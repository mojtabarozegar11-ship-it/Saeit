#!/usr/bin/env python3
"""Repair *only missing* first-party analytics markers on 8 pinned static pages.

Read-only by default. --apply requires a host-local private backup, atomic
same-directory file replacement, and a fingerprint race check immediately
before replacement. Never touches Django, payment, database, cron or factory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

WEBROOT = Path("/home/zomorod2/mojplaywin.com")
BACKUP_ROOT = Path("/home/zomorod2/separated-backups")
PAGES = (
    "store/index.html",
    "moj-prop/index.html",
    "moj-prop/starter-30-trx/index.html",
    "moj-prop/catalog/index.html",
    "moj-prop/rules/index.html",
    "moj-prop/payment/index.html",
    "moj-prop/contact/index.html",
    "moj-prop/signals/index.html",
)
MARKER = '<script defer src="/mpw-measure/tracker.js"></script>'
SCRIPT = "mpw-measure/tracker.js"


def fingerprint(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def inspect_page(path: Path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 256 * 1024:
        raise RuntimeError("PAGE_MISSING_OR_UNSAFE:" + path.name)
    raw = path.read_bytes()
    try:
        html = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise RuntimeError("NOT_UTF8:" + path.name)
    count = html.count(SCRIPT)
    if count > 1 or (count == 1 and html.count(MARKER) != 1):
        raise RuntimeError("AMBIGUOUS_TRACKER:" + path.name)
    if count == 1:
        return raw, raw, "present"
    if len(re.findall(r"</body\s*>", html, flags=re.I)) != 1:
        raise RuntimeError("AMBIGUOUS_BODY:" + path.name)
    replacement = re.sub(r"</body\s*>", MARKER + "\n</body>", html,
                         flags=re.I, count=1)
    return raw, replacement.encode("utf-8"), "missing"


def plan(webroot: Path):
    if not webroot.is_dir() or webroot.is_symlink():
        raise RuntimeError("WEBROOT_UNSAFE")
    tracker = webroot / SCRIPT
    if not tracker.is_file() or tracker.is_symlink():
        raise RuntimeError("TRACKER_MISSING")
    out = {}
    for relative in PAGES:
        old, new, status = inspect_page(webroot / relative)
        out[relative] = {
            "status": status, "original_sha256": fingerprint(old),
            "modified_sha256": fingerprint(new), "bytes_delta": len(new) - len(old),
        }
    return out


def atomic_replace(target: Path, payload: bytes, mode: int):
    fd, name = tempfile.mkstemp(prefix=".mpw-measure-repair-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as h:
            h.write(payload)
            h.flush()
            os.fsync(h.fileno())
        os.chmod(name, mode)
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def repair(webroot: Path, backup_root: Path, snapshot):
    missing = [n for n, info in snapshot.items() if info["status"] == "missing"]
    if not missing:
        return {"status": "already_healthy", "changed": [], "backup": None}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_root / stamp[:8] / ("mpw-measure-static-repair-" + stamp)
    if backup.exists():
        raise RuntimeError("BACKUP_EXISTS")
    backup.mkdir(parents=True, mode=0o700)
    os.chmod(backup, 0o700)
    saved = {}
    # Stage and retain all original bytes BEFORE making any live write.
    for relative in missing:
        target = webroot / relative
        original, revised, state = inspect_page(target)
        if (state != "missing" or fingerprint(original)
                != snapshot[relative]["original_sha256"]):
            raise RuntimeError("PAGE_CHANGED_BEFORE_BACKUP:" + relative)
        destination = backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(original)
        os.chmod(destination, 0o600)
        saved[relative] = {
            "source_sha256": fingerprint(original),
            "new_sha256": fingerprint(revised),
        }
    manifest = backup / "manifest.json"
    manifest.write_text(json.dumps({
        "schema": "mpw.measure.live_repair_backup.v1",
        "timestamp_utc": stamp,
        "source": "exact eight pinned static pages",
        "files": saved,
        "restore": "Only with separately authorized scoped restore",
    }, indent=2))
    os.chmod(manifest, 0o600)
    changed = []
    for relative in missing:
        target = webroot / relative
        old, new, state = inspect_page(target)
        if state != "missing" or fingerprint(old) != saved[relative]["source_sha256"]:
            raise RuntimeError("CONCURRENT_CONTENT_DRIFT:" + relative)
        mode = stat.S_IMODE(target.stat().st_mode)
        atomic_replace(target, new, mode)
        verified, _, state = inspect_page(target)
        if fingerprint(verified) != saved[relative]["new_sha256"] or state != "present":
            raise RuntimeError("POST_WRITE_MISMATCH:" + relative)
        changed.append(relative)
    return {"status": "repaired", "changed": changed, "backup": str(backup)}


def main():
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--apply", action="store_true")
    args = arg.parse_args()
    state = plan(WEBROOT)
    missing = [name for name, d in state.items() if d["status"] == "missing"]
    if args.apply:
        result = repair(WEBROOT, BACKUP_ROOT, state)
        if set(name for name, d in plan(WEBROOT).items() if d["status"] == "missing"):
            raise RuntimeError("SOME_TRACKERS_STILL_MISSING")
        print(json.dumps({"result": result, "checked_pages": len(PAGES)}))
    else:
        print(json.dumps({
            "status": "preflight", "checked_pages": len(PAGES),
            "missing": missing, "present": len(PAGES) - len(missing),
            "no_write": True,
        }, indent=2))


if __name__ == "__main__":
    main()
