#!/usr/bin/env python3
"""Guarded, byte-exact split of the approved Zomorod homepage runtime.

The existing theme, content, card order, links and CSS are left untouched.
The large inline manifest and its dependent renderer become one cacheable,
deferred JavaScript asset so the browser can paint the homepage first.

Default mode is read-only. Staging creates files only in an explicit directory.
Publishing requires a separate explicit --publish and the pinned live SHA.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone


APPROVED_HOME_SHA256 = "0c8a0a26780645281da8d19cbc9e5926886922dcd37d56d0a06952a627a76585"
LIVE_ROOT = Path("/home/zomorod2/public_html")
PRIVATE_BACKUPS = Path("/home/zomorod2/.private/zomorod-home-speed")
MANIFEST_OPEN = b"<script>window.ZOMOROD_ORBIT_DATA="
RENDERER_OPEN = b"<script>/* Zomorod Melal | offline design prototype:"
SCRIPT_CLOSE = b"</script>"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def one_script(source: bytes, opening: bytes) -> tuple[bytes, bytes]:
    if source.count(opening) != 1:
        raise ValueError(f"Script marker is not unique: {opening[:60]!r}")
    begin = source.index(opening)
    end_tag = source.find(SCRIPT_CLOSE, begin + len(opening))
    if end_tag < 0:
        raise ValueError("Unclosed script block")
    end = end_tag + len(SCRIPT_CLOSE)
    return source[begin:end], source[begin + len(b"<script>"):end_tag]


def transform(source: bytes) -> tuple[bytes, bytes, str]:
    if sha(source) != APPROVED_HOME_SHA256:
        raise ValueError("Live homepage SHA differs from the approved immutable baseline")

    manifest_tag, manifest_js = one_script(source, MANIFEST_OPEN)
    renderer_tag, renderer_js = one_script(source, RENDERER_OPEN)
    if source.index(manifest_tag) >= source.index(renderer_tag):
        raise ValueError("Unexpected dependency order")
    if b"window.ZOMOROD_ORBIT_DATA" not in manifest_js:
        raise ValueError("Manifest variable missing")
    if b"config.rows.map(buildShelf)" not in renderer_js:
        raise ValueError("Expected renderer missing")

    asset = manifest_js + b"\n" + renderer_js + b"\n"
    asset_name = f"zomorod-home-runtime-{sha(asset)[:20]}.js"
    public_path = "/static/site/zomorod-perf/" + asset_name
    replacement = f'<script defer src="{public_path}"></script>'.encode("ascii")

    output = source.replace(manifest_tag, replacement, 1).replace(renderer_tag, b"", 1)
    if output.count(replacement) != 1 or MANIFEST_OPEN in output or RENDERER_OPEN in output:
        raise ValueError("Unexpected transformed document")
    # Demonstrate that the original document can be reconstructed byte for byte.
    restored = output.replace(replacement, manifest_tag, 1)
    renderer_location = source.index(renderer_tag)
    prefix = source[:renderer_location].replace(manifest_tag, replacement, 1)
    insert_at = len(prefix)
    restored = restored[:insert_at + len(manifest_tag) - len(replacement)] + renderer_tag + restored[insert_at + len(manifest_tag) - len(replacement):]
    if restored != source:
        # The invariant also prevents accidental edits to approved layout or copy.
        raise ValueError("Source reversibility check failed")

    return output, asset, asset_name


def atomic_new(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    if path.is_symlink() or path.exists():
        raise FileExistsError(f"Refusing to overwrite existing asset: {path}")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".zm-", delete=False) as f:
        pending = Path(f.name)
        try:
            os.fchmod(f.fileno(), mode)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        except Exception:
            pending.unlink(missing_ok=True)
            raise
    try:
        # Link creation is exclusive: unlike os.replace, it never clobbers a
        # same-name file created by another publisher after our preflight.
        os.link(pending, path, follow_symlinks=False)
    finally:
        pending.unlink(missing_ok=True)
    if path.read_bytes() != data:
        raise RuntimeError(f"Written asset verification failed: {path}")


def atomic_replace(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".zm-", delete=False) as f:
        pending = Path(f.name)
        try:
            os.fchmod(f.fileno(), path.stat().st_mode & 0o777)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        except Exception:
            pending.unlink(missing_ok=True)
            raise
    try:
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--stage", type=Path, help="Write candidate files to this non-production directory")
    parser.add_argument("--publish", action="store_true", help="Explicit guarded live cPanel publication")
    args = parser.parse_args()
    if args.stage and args.publish:
        parser.error("--stage and --publish are mutually exclusive")

    if args.source.is_symlink():
        raise ValueError("Symlink source refused")
    source = args.source.resolve(strict=True)
    original = source.read_bytes()
    page, asset, asset_name = transform(original)
    summary = {"approved_source_sha256": sha(original), "candidate_html_sha256": sha(page),
               "runtime_sha256": sha(asset), "old_html_bytes": len(original),
               "new_html_bytes": len(page), "new_deferred_js_bytes": len(asset),
               "asset": "/static/site/zomorod-perf/" + asset_name}

    if args.stage:
        destination = args.stage.resolve()
        if destination == LIVE_ROOT or LIVE_ROOT in destination.parents:
            raise ValueError("Staging must be outside production")
        destination.mkdir(parents=True, exist_ok=True)
        atomic_new(destination / "index.html", page, 0o644)
        atomic_new(destination / asset_name, asset, 0o644)
        print(json.dumps({**summary, "mode": "staged", "folder": str(destination)}, indent=2))
        return

    if not args.publish:
        print(json.dumps({**summary, "mode": "read_only"}, indent=2))
        return

    if source != LIVE_ROOT / "index.html":
        raise ValueError("Publishing allowed only for the pinned Zomorod homepage")
    if any(p.is_symlink() for p in (LIVE_ROOT, LIVE_ROOT / "static", LIVE_ROOT / "static/site",
                                     LIVE_ROOT / "static/site/zomorod-perf")):
        raise ValueError("Symlink in live asset path")
    if any(p.is_symlink() for p in (PRIVATE_BACKUPS.parent, PRIVATE_BACKUPS)):
        raise ValueError("Symlink in private backup path")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    PRIVATE_BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = PRIVATE_BACKUPS / f"index-{stamp}-{sha(original)[:12]}.html"
    atomic_new(backup, original, 0o600)
    asset_path = LIVE_ROOT / "static/site/zomorod-perf" / asset_name
    try:
        atomic_new(asset_path, asset, 0o644)
        if sha(source.read_bytes()) != APPROVED_HOME_SHA256:
            raise RuntimeError("Homepage changed during publication preflight")
        atomic_replace(source, page)
        if sha(source.read_bytes()) != sha(page) or asset_path.read_bytes() != asset:
            raise RuntimeError("Post-publication local parity check failed")
    except Exception:
        # Only restore if our candidate is present; never overwrite a third party edit.
        if source.exists() and sha(source.read_bytes()) == sha(page):
            atomic_replace(source, original)
        raise
    print(json.dumps({**summary, "mode": "published_local_checks_only",
                      "backup": str(backup), "needs_origin_and_public_http_verification": True}, indent=2))


if __name__ == "__main__":
    main()
