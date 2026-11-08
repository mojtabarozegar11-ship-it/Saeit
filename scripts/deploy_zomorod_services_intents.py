"""Release exactly four reviewed services inquiry links on the cPanel host.

All customer data, the calculator, and every unrelated page byte are preserved.
No GitHub Action or VPS is required. This module never runs on import.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from urllib.request import Request, urlopen


MAX_HTML_BYTES = 2_000_000
PUBLIC_URL = "https://zomorodmelal.ir/services/"
GENERIC_URL = b"/ask-master/index.php?service=1"
LINKS = (
    ("استعلام ارزیابی اقتصادی ←", "economics"),
    ("استعلام مدیریت منابع ←", "water"),
    ("استعلام امکان‌سنجی ←", "feasibility"),
    ("درخواست تحلیل اقتصادی تخصصی مزرعه", "economics"),
)
ANCHOR = re.compile(rb"<a\b[^>]*>[^<]*</a>", re.DOTALL)
# Only a real, whitespace-delimited HTML href counts. A word boundary also
# matches data-href / xlink:href and could silently validate a wrong target.
HREF = re.compile(rb'(?<=\s)href="([^"]+)"')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Missing or symlinked file: " + path.name)
    if not 0 < path.stat().st_size <= MAX_HTML_BYTES:
        raise RuntimeError("Empty or oversized file: " + path.name)


def find_links(source: bytes) -> dict[str, tuple[bytes, bytes]]:
    """Require one simple anchor for each exact, user-visible service label."""
    if not 0 < len(source) <= MAX_HTML_BYTES:
        raise ValueError("Missing or oversized HTML")
    found: dict[str, tuple[bytes, bytes]] = {}
    labels = {label.encode("utf-8"): label for label, _topic in LINKS}
    for match in ANCHOR.finditer(source):
        raw = match.group(0)
        visible = raw[raw.find(b">") + 1: -len(b"</a>")].strip()
        label = labels.get(visible)
        if label is None:
            continue
        if label in found:
            raise ValueError("Duplicate specialist link: " + label)
        attributes = raw[:raw.index(b">")]
        hrefs = HREF.findall(attributes)
        if len(hrefs) != 1:
            raise ValueError("Specialist link requires exactly one real href: " + label)
        found[label] = (raw, hrefs[0])
    if len(found) != len(LINKS):
        raise ValueError("Missing or altered specialist links")
    return found


def expected_href(topic: str) -> bytes:
    return GENERIC_URL + b"&amp;topic=" + topic.encode("ascii")


def prepare(current: bytes, approved: bytes) -> tuple[str, bytes]:
    """Return a scoped, reversible HTML patch or refuse partial/drifted state."""
    reviewed = find_links(approved)
    live = find_links(current)
    for label, topic in LINKS:
        if reviewed[label][1] != expected_href(topic):
            raise ValueError("Approved source has an unexpected destination: " + label)
    live_urls = [live[label][1] for label, _ in LINKS]
    if all(url == expected_href(topic) for url, (_, topic) in zip(live_urls, LINKS)):
        return "already_deployed", current
    if any(url != GENERIC_URL for url in live_urls):
        raise RuntimeError("Partial release or unexpected live link: no overwrite")
    updated = current
    reversals = []
    for label, topic in LINKS:
        old_anchor = live[label][0]
        # Replace the exact, validated href token, never an earlier data-href
        # containing the same text. Its byte offset is within this anchor.
        head = old_anchor[:old_anchor.index(b">")]
        real_href = HREF.search(head)
        if real_href is None or real_href.group(1) != GENERIC_URL:
            raise RuntimeError("Live href changed before scoped replacement: " + label)
        new_anchor = (old_anchor[:real_href.start(1)] + expected_href(topic)
                      + old_anchor[real_href.end(1):])
        if new_anchor == old_anchor or updated.count(old_anchor) != 1:
            raise RuntimeError("Ambiguous scoped anchor replacement: " + label)
        updated = updated.replace(old_anchor, new_anchor, 1)
        reversals.append((old_anchor, new_anchor))
    if any(find_links(updated)[label][1] != expected_href(topic) for label, topic in LINKS):
        raise RuntimeError("New specialist targets not intact")
    restored = updated
    for old_anchor, new_anchor in reversed(reversals):
        if restored.count(new_anchor) != 1:
            raise RuntimeError("Irreversible anchor replacement")
        restored = restored.replace(new_anchor, old_anchor, 1)
    if restored != current:
        raise RuntimeError("Unrelated HTML bytes changed")
    return "ready", updated


def write_exclusive(path: Path, content: bytes, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, mode)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def atomic_replace(target: Path, content: bytes, mode: int) -> None:
    tmp = target.with_name(target.name + ".zm-intents-stage")
    if tmp.exists() or tmp.is_symlink():
        raise RuntimeError("A previous staging file exists; refusing overwrite")
    write_exclusive(tmp, content, mode)
    try:
        os.chmod(tmp, mode)
        os.replace(tmp, target)
        fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        tmp.unlink(missing_ok=True)


def verify_public(release_id: str) -> None:
    request = Request(PUBLIC_URL + "?intent_release=" + release_id,
                      headers={"Cache-Control": "no-cache", "User-Agent": "Zomorod-Intents-Release/1.0"})
    with urlopen(request, timeout=25) as response:
        if response.status != 200 or not response.geturl().startswith(PUBLIC_URL):
            raise RuntimeError("Public page verification got an unexpected response")
        page = response.read(MAX_HTML_BYTES + 1)
    links = find_links(page)
    if any(links[label][1] != expected_href(topic) for label, topic in LINKS):
        raise RuntimeError("Public page still exposes a generic specialist link")
    if b'id="zm-margin-download"' not in page:
        raise RuntimeError("Existing CSV calculator is missing from public HTML")


def release(*, target: Path, approved: bytes, expected_sha: str,
            backup_dir: Path, verify) -> dict[str, str]:
    check_regular(target)
    if target.parent.is_symlink() or backup_dir.parent.is_symlink():
        raise RuntimeError("Symlinked services or backup directory refused")
    original = target.read_bytes()
    if sha256(original) != expected_sha:
        raise RuntimeError("Live file hash changed since read-only preflight")
    state, updated = prepare(original, approved)
    if state == "already_deployed":
        verify()
        return {"state": state, "sha256": expected_sha}
    if backup_dir.exists() or backup_dir.is_symlink():
        raise RuntimeError("Release ID already used")
    backup_dir.mkdir(mode=0o700)
    backup = backup_dir / "services-original.html"
    write_exclusive(backup, original, 0o600)
    if backup.read_bytes() != original:
        raise RuntimeError("Private rollback backup mismatch")
    manifest = {"original_sha256": expected_sha, "new_sha256": sha256(updated),
                "scoped_links": len(LINKS)}
    write_exclusive(backup_dir / "manifest.json", json.dumps(manifest).encode(), 0o600)
    mode = stat.S_IMODE(target.stat().st_mode)
    if target.read_bytes() != original:
        raise RuntimeError("Concurrent live change detected")
    try:
        atomic_replace(target, updated, mode)
        if target.read_bytes() != updated:
            raise RuntimeError("Written file does not match intended patch")
        verify()
    except BaseException:
        if target.is_file() and not target.is_symlink() and target.read_bytes() == updated:
            atomic_replace(target, original, mode)
            print("ZM_SERVICE_INTENTS_ROLLBACK=restored", flush=True)
        else:
            print("ZM_SERVICE_INTENTS_ROLLBACK=manual_review", flush=True)
        raise
    print("ZM_SERVICE_INTENTS_RELEASE=verified", flush=True)
    return {"state": "deployed", **manifest}


def main(argv: list[str]) -> None:
    if len(argv) not in (3, 6):
        raise SystemExit("usage: deploy_zomorod_services_intents.py APPROVED.html check | APPROVED.html deploy RUNID-ATTEMPT EXPECTED_SHA256 CONFIRM_SERVICE_INTENTS")
    approved_path = Path(argv[1])
    check_regular(approved_path)
    home = Path.home()
    if home.name != "zomorod2":
        raise SystemExit("Refusing to run outside the approved hosting account")
    target = home / "public_html/services/index.html"
    check_regular(target)
    approved = approved_path.read_bytes()
    current = target.read_bytes()
    if argv[2] == "check" and len(argv) == 3:
        state, _ = prepare(current, approved)
        print(json.dumps({"state": state, "live_sha256": sha256(current),
                          "scoped_links": len(LINKS)}, sort_keys=True))
        return
    if len(argv) != 6 or argv[2] != "deploy" or argv[5] != "CONFIRM_SERVICE_INTENTS":
        raise SystemExit("Explicit scoped release confirmation required")
    release_id, expected_sha = argv[3], argv[4]
    if not re.fullmatch(r"[0-9]{1,20}-[0-9]{1,4}", release_id):
        raise SystemExit("Invalid release identifier")
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
        raise SystemExit("Invalid expected live SHA256")
    parent = home / ".backups/zomorod-services-intents"
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    result = release(target=target, approved=approved, expected_sha=expected_sha,
                     backup_dir=parent / release_id, verify=lambda: verify_public(release_id))
    print("ZM_SERVICE_INTENTS_STATE=" + result["state"], flush=True)


if __name__ == "__main__":
    main(sys.argv)
