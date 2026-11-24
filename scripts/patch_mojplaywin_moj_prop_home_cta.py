#!/usr/bin/env python3
"""Safely patch only the reviewed Signal Desk CTA on the live Moj Prop home.

This is intentionally narrower than the catalog publisher: it changes exactly
the two legacy Signal Desk links on the owner-maintained static home, preserves
the rest of the file byte-for-byte, writes a private rollback copy, and refuses
all unexpected live content.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

HOME = Path("/home/zomorod2")
ROUTE = HOME / "mojplaywin.com" / "moj-prop"
TARGET = ROUTE / "index.html"
BACKUPS = HOME / ".mojplaywin-moj-prop-home-cta-backups-v1"
SCHEMA = "mojprop.home-cta.v1"
OLD = 'href="/commerce/book/1467/">Buy Signal Desk — $9.90'
NEW = ('href="/commerce/book/1467/?utm_source=moj_prop&utm_medium=prop_page'
       '&utm_campaign=signal_weekly_brief&utm_content=signal_cta">'
       'Buy Weekly Brief — $9.90')


def fail(message: str) -> "NoReturn":
    raise RuntimeError(message)


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[0-9]{1,20}", value):
        fail("Invalid deployment run ID")
    return value


def safe_sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        fail("Invalid deployment commit SHA")
    return value


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_host() -> None:
    if os.geteuid() <= 0:
        fail("Root execution is refused")
    if not ROUTE.is_dir() or ROUTE.is_symlink():
        fail("Moj Prop route is missing or symlinked")
    if TARGET.is_symlink() or not TARGET.is_file():
        fail("Moj Prop home is not a regular file")
    info = TARGET.stat()
    if info.st_uid != os.geteuid() or info.st_mode & 0o002:
        fail("Moj Prop home owner or permissions are unsafe")


def verify_backup_root(create: bool) -> None:
    parent = BACKUPS.parent
    if parent.is_symlink() or not parent.is_dir():
        fail("Backup parent is not trusted")
    parent_info = parent.stat()
    if parent_info.st_uid != os.geteuid() or parent_info.st_mode & stat.S_IWOTH:
        fail("Backup parent owner or mode is unsafe")
    if BACKUPS.is_symlink():
        fail("Backup root is symlinked")
    if BACKUPS.exists():
        info = BACKUPS.stat()
        if not info.st_uid == os.geteuid() or info.st_mode & 0o077:
            fail("Backup root owner or mode is unsafe")
    elif create:
        BACKUPS.mkdir(mode=0o700)
    else:
        fail("Backup root is missing")


def atomic_write(data: bytes, mode: int) -> None:
    fd, name = tempfile.mkstemp(prefix=".index.html.mojcta-", dir=str(ROUTE))
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, TARGET)
    finally:
        if temporary.exists():
            temporary.unlink()


def deploy(run_id: str, commit_sha: str) -> None:
    run_id = safe_id(run_id)
    commit_sha = safe_sha(commit_sha)
    assert_host()
    verify_backup_root(create=True)
    backup = BACKUPS / ("home-cta-" + run_id)
    if backup.exists():
        fail("A backup for this run already exists")
    raw = TARGET.read_bytes()
    old_count = raw.count(OLD.encode("utf-8"))
    new_count = raw.count(NEW.encode("utf-8"))
    if new_count == 2 and old_count == 0:
        print("MOJ_PROP_HOME_CTA_ALREADY_PATCHED")
        return
    if old_count != 2 or new_count:
        fail(f"Unexpected CTA state old={old_count} new={new_count}")
    if b"Buy Signal Desk" not in raw or b"/commerce/book/1467/" not in raw:
        fail("Reviewed Signal Desk marker is missing")
    updated = raw.replace(OLD.encode("utf-8"), NEW.encode("utf-8"))
    if updated.count(NEW.encode("utf-8")) != 2 or updated.count(OLD.encode("utf-8")):
        fail("Exact CTA replacement verification failed")
    backup.mkdir(mode=0o700)
    (backup / "index.html").write_bytes(raw)
    os.chmod(backup / "index.html", 0o600)
    manifest = {
        "schema": SCHEMA,
        "run_id": run_id,
        "commit_sha": commit_sha,
        "path": "moj-prop/index.html",
        "before_sha": digest(raw),
        "after_sha": digest(updated),
        "old_count": old_count,
        "new_count": 2,
        "mode": TARGET.stat().st_mode & 0o777,
        "rolled_back": False,
    }
    (backup / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    os.chmod(backup / "manifest.json", 0o600)
    atomic_write(updated, manifest["mode"])
    actual = TARGET.read_bytes()
    if digest(actual) != manifest["after_sha"] or actual.count(NEW.encode("utf-8")) != 2:
        fail("Live home CTA post-write verification failed")
    print("MOJ_PROP_HOME_CTA_PATCH=PASS")
    print("MOJ_PROP_HOME_CTA_OLD_COUNT=0")
    print("MOJ_PROP_HOME_CTA_NEW_COUNT=2")
    print("MOJ_PROP_HOME_CTA_BACKUP=" + str(backup))


def rollback(run_id: str) -> None:
    run_id = safe_id(run_id)
    assert_host()
    verify_backup_root(create=False)
    backup = BACKUPS / ("home-cta-" + run_id)
    manifest_path = backup / "manifest.json"
    saved_path = backup / "index.html"
    if backup.is_symlink() or not backup.is_dir() or manifest_path.is_symlink() or saved_path.is_symlink():
        fail("Unsafe rollback backup")
    manifest = json.loads(manifest_path.read_text("utf-8"))
    if manifest.get("schema") != SCHEMA or manifest.get("run_id") != run_id:
        fail("Rollback manifest identity mismatch")
    if manifest.get("rolled_back") is True:
        print("MOJ_PROP_HOME_CTA_ALREADY_ROLLED_BACK")
        return
    current = TARGET.read_bytes()
    if digest(current) != manifest.get("after_sha"):
        fail("Refusing rollback after subsequent live modification")
    saved = saved_path.read_bytes()
    if digest(saved) != manifest.get("before_sha"):
        fail("Rollback backup checksum mismatch")
    atomic_write(saved, int(manifest["mode"]))
    if digest(TARGET.read_bytes()) != manifest["before_sha"]:
        fail("Rollback verification failed")
    manifest["rolled_back"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("MOJ_PROP_HOME_CTA_ROLLBACK=PASS")


def main() -> None:
    if len(sys.argv) < 3:
        fail("Usage: deploy RUN_ID COMMIT_SHA | rollback RUN_ID")
    action = sys.argv[1]
    if action == "deploy" and len(sys.argv) == 4:
        deploy(sys.argv[2], sys.argv[3])
    elif action == "rollback" and len(sys.argv) == 3:
        rollback(sys.argv[2])
    else:
        fail("Invalid arguments")


if __name__ == "__main__":
    main()
