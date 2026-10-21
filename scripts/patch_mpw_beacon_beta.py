#!/usr/bin/env python3
"""Bounded repair for one pre-start Beacon Labyrinth canvas error.

Never touches shared Django, Passenger, payment, root .htaccess or other games.
"""
import hashlib
import json
import os
import pwd
import re
import shutil
import sys
from pathlib import Path

ACCOUNT = Path("/home/zomorod2")
SITE = ACCOUNT / "mojplaywin.com"
RELEASE = SITE / "game-releases" / "20261021"
DEST = RELEASE / "beacon-labyrinth" / "index.html"
RELEASE_MARKER = RELEASE / ".mojplaywin-five-games-owner.json"
BACKUPS = ACCOUNT / ".mojplaywin-game-backups"
OLD_BLOB_SHA = "0f2e7840def2e558b526ee70a9465f2f80b857b6"
MARKER_TEXT = "beacon-initial-frame-fix-20261021"

def blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def ids(run_id, commit):
    if not re.fullmatch(r"[0-9]{1,20}", run_id) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("Untrusted run identifiers")

def check_target():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Unexpected hosting identity")
    if SITE.is_symlink() or not SITE.is_dir() or not (SITE / "passenger_wsgi.py").is_file():
        raise RuntimeError("MojPlayWin site root not verified")
    for path in (RELEASE, RELEASE / "beacon-labyrinth", DEST, RELEASE_MARKER, RELEASE / ".htaccess"):
        if path.is_symlink():
            raise RuntimeError("Symlink in protected target")
    if not DEST.is_file() or not RELEASE_MARKER.is_file():
        raise RuntimeError("Owned beta target missing")
    owner = json.loads(RELEASE_MARKER.read_text(encoding="utf-8"))
    if owner.get("owner") != "mojplaywin-five-games-v2":
        raise RuntimeError("Release ownership mismatch")
    if "PassengerEnabled off" not in (RELEASE / ".htaccess").read_text(encoding="utf-8"):
        raise RuntimeError("Static beta namespace guard missing")
    if BACKUPS.is_symlink():
        raise RuntimeError("Backup path symlink")

def source(run_id):
    path = ACCOUNT / (".mpw-beacon-patch-" + run_id) / "site_patches/mojplaywin/20261021/beacon-labyrinth/index.html"
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Patch payload missing")
    raw = path.read_bytes()
    if not (19000 < len(raw) < 80000 and raw.count(MARKER_TEXT.encode()) == 1):
        raise RuntimeError("Patch marker/size guard failed")
    if b"https://mojplaywin.com/game-releases/20261021/beacon-labyrinth/index.html" not in raw:
        raise RuntimeError("Unexpected canonical")
    if b"if(!maze.length){a.fillBg(200);return}" not in raw:
        raise RuntimeError("Startup guard missing")
    return raw

def backup_paths(run_id):
    return BACKUPS / ("beacon-beta-before-" + run_id + ".html"), BACKUPS / ("beacon-beta-" + run_id + ".json")

def install(run_id, commit):
    ids(run_id, commit)
    check_target()
    payload = source(run_id)
    after = blob_sha(payload)
    current = DEST.read_bytes()
    before = blob_sha(current)
    if before == after:
        print("BEACON_BETA_PATCH_ALREADY_APPLIED")
        return
    if before != OLD_BLOB_SHA:
        raise RuntimeError("Live beta differs from pinned original; refuse overwrite")
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    backup, receipt = backup_paths(run_id)
    temp = DEST.parent / (".pending-beacon-fix-" + run_id)
    if any(p.exists() or p.is_symlink() for p in (backup, receipt, temp)):
        raise RuntimeError("Patch/backup collision")
    shutil.copyfile(DEST, backup)
    os.chmod(backup, 0o600)
    if blob_sha(backup.read_bytes()) != OLD_BLOB_SHA:
        raise RuntimeError("Original backup verification failed")
    try:
        temp.write_bytes(payload)
        os.chmod(temp, 0o644)
        if blob_sha(temp.read_bytes()) != after:
            raise RuntimeError("Pending patch integrity mismatch")
        receipt.write_text(json.dumps({"run_id":run_id,"commit":commit,"old":before,"new":after})+"\n",encoding="utf-8")
        os.chmod(receipt, 0o600)
        os.replace(temp, DEST)
    except Exception:
        # Fail closed; preserve backup for supervised recovery.
        if temp.exists() and not temp.is_symlink():
            temp.unlink()
        raise
    print("BEACON_BETA_PATCH_INSTALLED " + after)

def rollback(run_id, commit):
    ids(run_id, commit)
    check_target()
    backup, receipt = backup_paths(run_id)
    if not backup.is_file() or backup.is_symlink() or not receipt.is_file() or receipt.is_symlink():
        raise RuntimeError("Rollback receipt unavailable")
    record = json.loads(receipt.read_text(encoding="utf-8"))
    if record.get("run_id") != run_id or record.get("commit") != commit:
        raise RuntimeError("Rollback identity mismatch")
    if blob_sha(DEST.read_bytes()) != record.get("new") or blob_sha(backup.read_bytes()) != record.get("old"):
        raise RuntimeError("Rollback hashes differ: refusing overwrite")
    temp = DEST.parent / (".restore-beacon-fix-" + run_id)
    if temp.exists() or temp.is_symlink():
        raise RuntimeError("Restore path collision")
    shutil.copyfile(backup, temp)
    os.chmod(temp, 0o644)
    os.replace(temp, DEST)
    print("BEACON_BETA_RESTORED_FROM_VERIFIED_BACKUP")

if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in {"install","rollback"}:
        raise SystemExit("Usage: install|rollback RUN_ID COMMIT_SHA")
    {"install": install, "rollback": rollback}[sys.argv[1]](sys.argv[2],sys.argv[3])
