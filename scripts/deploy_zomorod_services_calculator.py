"""Safely release ONLY the farm calculator block of /services/index.html.

The live page may contain editorial and operational changes absent from GitHub.
An exact comparison of the legacy block protects those unrelated live bytes.
There is no automatic deployment: this script is invoked only by an explicitly
dispatched owner-controlled release workflow after source approval.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Callable
from urllib.request import Request, urlopen


MARKER = b"<!-- zm-farm-margin-calculator-20261106:client-only -->"
END_SCRIPT = b"</script>"
MAX_HTML_BYTES = 2_000_000
PUBLIC_URL = "https://zomorodmelal.ir/services/"


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def section(source: bytes) -> tuple[int, int, bytes]:
    if not 0 < len(source) <= MAX_HTML_BYTES or source.count(MARKER) != 1:
        raise ValueError("Missing, duplicate, or oversized farm calculator section")
    start = source.index(MARKER)
    close_section = source.find(b"</section>", start)
    open_script = source.find(b"<script>", start)
    close_script = source.find(END_SCRIPT, open_script)
    if not (start < close_section < open_script < close_script):
        raise ValueError("Calculator section/script boundaries are not intact")
    end = close_script + len(END_SCRIPT)
    block = source[start:end]
    if block.count(b'id="zm-margin-run"') != 1 or block.count(b"<script>") != 1:
        raise ValueError("Unexpected calculator block structure")
    return start, end, block


def expected_release(legacy: bytes, approved: bytes) -> tuple[bytes, bytes]:
    old = section(legacy)[2]
    new = section(approved)[2]
    if b'id="zm-margin-download"' in old:
        raise ValueError("Legacy baseline is not the approved pre-CSV version")
    for requirement in (
        b'id="zm-margin-download"',
        b"function resetPriorResult()",
        b"breakEvenPrice:yieldKg>0",
        b"Number.MAX_SAFE_INTEGER",
    ):
        if requirement not in new:
            raise ValueError("Approved calculator is missing a required safeguard")
    if old == new:
        raise ValueError("No reviewed change to release")
    return old, new


def write_exclusive(path: Path, content: bytes, mode: int = 0o600) -> None:
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def atomic_replace(target: Path, content: bytes, mode: int) -> None:
    tmp = target.with_name(target.name + ".zm-calculator-stage")
    if tmp.exists() or tmp.is_symlink():
        raise RuntimeError("Unresolved staging file; refusing overwrite")
    write_exclusive(tmp, content, mode)
    try:
        os.chmod(tmp, mode)
        os.replace(tmp, target)
        dir_fd = os.open(str(target.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        tmp.unlink(missing_ok=True)


def check_regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_HTML_BYTES:
        raise RuntimeError("Missing, symlinked, or oversized required file: " + path.name)


def release(
    *,
    legacy: bytes,
    approved: bytes,
    target: Path,
    backup_dir: Path,
    verify: Callable[[bytes], None],
) -> dict[str, str]:
    """Preserve all bytes outside the calculator and roll back verified failures."""
    check_regular(target)
    if target.parent.is_symlink():
        raise RuntimeError("Services directory is a symlink")
    old_block, new_block = expected_release(legacy, approved)
    original = target.read_bytes()
    start, end, live_block = section(original)
    if live_block == new_block:
        verify(new_block)
        return {"state": "already_deployed", "sha256": digest(original)}
    if live_block != old_block:
        raise RuntimeError("Live calculator differs from exact reviewed baseline; no overwrite")
    updated = original[:start] + new_block + original[end:]
    if updated.replace(new_block, old_block, 1) != original:
        raise RuntimeError("Unrelated bytes would change")
    if backup_dir.exists() or backup_dir.is_symlink():
        raise RuntimeError("Release backup already exists; refusing repeat")
    backup_dir.mkdir(mode=0o700, parents=False)
    original_backup = backup_dir / "services-original.html"
    write_exclusive(original_backup, original)
    if original_backup.read_bytes() != original:
        raise RuntimeError("Original backup verification failed")
    evidence = {
        "original_sha256": digest(original),
        "updated_sha256": digest(updated),
        "legacy_block_sha256": digest(old_block),
        "approved_block_sha256": digest(new_block),
        "bytes_preserved_outside_block": str(len(original) - len(old_block)),
    }
    write_exclusive(backup_dir / "manifest.json", json.dumps(evidence, sort_keys=True).encode())
    mode = target.stat().st_mode & 0o777
    if target.read_bytes() != original:
        raise RuntimeError("Concurrent live edit detected before write")
    try:
        atomic_replace(target, updated, mode)
        if target.read_bytes() != updated:
            raise RuntimeError("Deployment bytes differ from approved output")
        verify(new_block)
    except BaseException:
        if target.is_file() and not target.is_symlink() and target.read_bytes() == updated:
            atomic_replace(target, original, mode)
            print("ZM_SERVICES_ROLLBACK=restored_original", flush=True)
        else:
            print("ZM_SERVICES_ROLLBACK=concurrent_edit_manual_review", flush=True)
        raise
    print("ZM_SERVICES_RELEASE=verified", flush=True)
    print("ZM_SERVICES_ORIGINAL_SHA256=" + evidence["original_sha256"], flush=True)
    print("ZM_SERVICES_NEW_SHA256=" + evidence["updated_sha256"], flush=True)
    return {"state": "deployed", **evidence}


def verify_public(block: bytes, release_id: str) -> None:
    request = Request(PUBLIC_URL + "?calculator_release=" + release_id,
                      headers={"Cache-Control": "no-cache", "User-Agent": "Zomorod-Scoped-Release/1.0"})
    with urlopen(request, timeout=25) as response:
        final_url = response.geturl()
        if response.status != 200 or not final_url.startswith(PUBLIC_URL):
            raise RuntimeError("Public endpoint returned an unexpected response")
        page = response.read(MAX_HTML_BYTES + 1)
    if len(page) > MAX_HTML_BYTES or any(key not in page for key in (
        b'id="zm-margin-download"',
        b"breakEvenPrice:yieldKg>0",
        b"input.addEventListener('input',resetPriorResult)",
    )):
        raise RuntimeError("Public HTML does not expose the new verified calculator")
    if digest(section(page)[2]) != digest(block):
        raise RuntimeError("Public calculator block does not match approved release")


def main(argv: list[str]) -> None:
    if len(argv) != 3:
        raise SystemExit("usage: deploy_zomorod_services_calculator.py STAGE_DIR RUNID-ATTEMPT")
    stage, release_id = Path(argv[1]), argv[2]
    if not re.fullmatch(r"[0-9]{1,20}-[0-9]{1,4}", release_id):
        raise SystemExit("Invalid scoped release identifier")
    for path in (stage, stage / "legacy_services.html", stage / "services.html"):
        if path.is_symlink():
            raise SystemExit("Symlinked stage refused")
    check_regular(stage / "legacy_services.html")
    check_regular(stage / "services.html")
    home = Path.home()
    target = home / "public_html/services/index.html"
    backup_parent = home / ".backups/zomorod-services-calculator"
    backup_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    result = release(
        legacy=(stage / "legacy_services.html").read_bytes(),
        approved=(stage / "services.html").read_bytes(),
        target=target,
        backup_dir=backup_parent / release_id,
        verify=lambda block: verify_public(block, release_id),
    )
    print("ZM_SERVICES_STATE=" + result["state"], flush=True)


if __name__ == "__main__":
    main(sys.argv)
