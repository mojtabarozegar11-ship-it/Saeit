#!/usr/bin/env python3
"""Scoped, fail-closed PICM-only cPanel release. No database or factory operations."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import sys
import tempfile

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
SITE = HOME / "mojplaywin.com"
BACKUPS = HOME / ".mojplaywin-backups"
FILES = (
    "core/picm_views.py",
    "templates/picm/index.html",
    "templates/picm/text_image.js",
)
# Original main-branch Git blob SHA values; refuse unknown live versions.
BASE_BLOBS = (
    "9193373fb0543d51b955bd6e284389d6005bd030",
    "3621070ee480e12ee091046622362d17961afd69",
    "0194b1655b8a0add4c3650a40cda84ec6081521d",
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(("blob " + str(len(raw)) + "\0").encode() + raw).hexdigest()


def stage(run):
    return HOME / (".picm-independent-stage-" + run)


def backup(run):
    return BACKUPS / ("picm-independent-" + run)


def guard(run):
    if not re.fullmatch(r"[0-9]{1,20}", run):
        raise RuntimeError("PICM_INVALID_RUN")
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("PICM_INVALID_HOST_USER")
    for root in (APP, SITE):
        if root.is_symlink() or not root.is_dir():
            raise RuntimeError("PICM_INVALID_APP_ROOT")
    entry = SITE / "passenger_wsgi.py"
    if entry.is_symlink() or not entry.is_file() or "Saeit-staging" not in entry.read_text(errors="replace"):
        raise RuntimeError("PICM_WRONG_PASSENGER_TARGET")
    if not (HOME / ".picm-queue/.owner-user-id").is_file():
        raise RuntimeError("PICM_OWNER_BINDING_MISSING")
    for name in FILES:
        file = APP / name
        if file.is_symlink() or file.parent.is_symlink() or not file.is_file():
            raise RuntimeError("PICM_LIVE_FILE_MISSING_OR_UNSAFE")


def write_atomic(file, raw, mode):
    if file.is_symlink() or file.parent.is_symlink():
        raise RuntimeError("PICM_UNSAFE_WRITE")
    fd, temporary = tempfile.mkstemp(prefix=".picm-capacity-", dir=file.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as fp:
            fp.write(raw)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temporary, file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def restart():
    for root in (APP, SITE):
        folder = root / "tmp"
        if folder.is_symlink():
            raise RuntimeError("PICM_INVALID_RESTART_PATH")
        folder.mkdir(exist_ok=True)
        marker = folder / "restart.txt"
        if marker.is_symlink():
            raise RuntimeError("PICM_INVALID_RESTART_MARKER")
        marker.touch()


def restore(run):
    guard(run)
    b = backup(run)
    manifest = b / "manifest.json"
    if b.is_symlink() or manifest.is_symlink() or not manifest.is_file():
        raise RuntimeError("PICM_BACKUP_MISSING")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("run") != run:
        raise RuntimeError("PICM_BACKUP_RUN_MISMATCH")
    # Check all files before changing any one of them.
    records = []
    for record in data["files"]:
        name = record["name"]
        if name not in FILES:
            raise RuntimeError("PICM_ROLLBACK_SCOPE_INVALID")
        target = APP / name
        saved = b / name
        if saved.is_symlink() or not saved.is_file() or target.is_symlink() or not target.is_file():
            raise RuntimeError("PICM_ROLLBACK_FILE_MISSING")
        previous = saved.read_bytes()
        if digest(previous) != record["original_sha"]:
            raise RuntimeError("PICM_BACKUP_DIGEST_MISMATCH")
        if digest(target.read_bytes()) not in (record["original_sha"], record["new_sha"]):
            raise RuntimeError("PICM_CONCURRENT_CHANGE_REFUSE_ROLLBACK")
        records.append((target, previous, record["mode"]))
    for target, previous, mode in records:
        write_atomic(target, previous, mode)
    restart()
    print("PICM_PRIVATE_CAPACITY_ROLLBACK_OK")


def deploy(run, expected):
    guard(run)
    if len(expected) != len(FILES) or not all(re.fullmatch(r"[a-f0-9]{64}", v) for v in expected):
        raise RuntimeError("PICM_BAD_CANDIDATE_ARGS")
    st = stage(run)
    b = backup(run)
    if st.is_symlink() or not st.is_dir() or b.exists() or b.is_symlink():
        raise RuntimeError("PICM_STAGE_OR_BACKUP_INVALID")
    candidate = []
    records = []
    for name, base, sha in zip(FILES, BASE_BLOBS, expected):
        staged = st / name
        target = APP / name
        if staged.is_symlink() or not staged.is_file():
            raise RuntimeError("PICM_STAGE_FILE_MISSING")
        raw = staged.read_bytes()
        old = target.read_bytes()
        if digest(raw) != sha or len(raw) < 1500:
            raise RuntimeError("PICM_CANDIDATE_INTEGRITY_FAILURE")
        if blob(old) != base:
            raise RuntimeError("PICM_LIVE_FILE_SHA_MISMATCH_REFUSE")
        candidate.append((target, raw, target.stat().st_mode & 0o777))
        records.append({"name": name, "original_sha": digest(old), "new_sha": sha,
                        "mode": target.stat().st_mode & 0o777})
    b.mkdir(mode=0o700, parents=True)
    if b.is_symlink():
        raise RuntimeError("PICM_BACKUP_UNSAFE")
    for record in records:
        name = record["name"]
        dst = b / name
        dst.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copy2(APP / name, dst)
        dst.chmod(0o600)
    manifest = json.dumps({"run": run, "files": records}, separators=(",", ":")).encode() + b"\n"
    write_atomic(b / "manifest.json", manifest, 0o600)
    changed = False
    try:
        for target, raw, mode in candidate:
            write_atomic(target, raw, mode)
            changed = True
        restart()
    except Exception:
        if changed:
            restore(run)
        raise
    print("PICM_PRIVATE_CAPACITY_SCOPED_RELEASE_OK")
    print("PICM_PRIVATE_CAPACITY_BACKUP_RUN=" + run)


if __name__ == "__main__":
    if len(sys.argv) == 6 and sys.argv[1] == "deploy":
        deploy(sys.argv[2], sys.argv[3:])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        restore(sys.argv[2])
    else:
        raise SystemExit("Usage: deploy RUN VIEW_SHA HTML_SHA JS_SHA | rollback RUN")
