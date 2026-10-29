#!/usr/bin/env python3
"""S-01: non-destructive, private checkout source preimage snapshot.

Only copies the exact, pinned 5 KB checkout source into an existing 0700
non-web backup directory. No app/DB edits, restart, payment or customer reads.
An existing partial/corrupt snapshot fails closed; no overwrite or cleanup.
This is LOCAL recovery only, NOT an independent off-host restore proof.
"""
import fcntl
import hashlib
import json
import os
import pwd
import stat
from pathlib import Path

EXPECTED_SHA256 = "f33d80b7e843a66c9a55d8a8da46d5fb6049fb4c487f8f559c3471cfd42cdf74"
ROOT = Path("/home/zomorod2")
WSGI_MARKER = "APP='/home/zomorod2/Saeit-staging'"
MIN_FREE = 20 * 1024 * 1024
MAX_SOURCE = 100_000
STEM = "mpw-checkout-csp-preimage-" + EXPECTED_SHA256[:16]


def require_regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RuntimeError("unexpected source/backup file type")
    return info


def require_private_dir(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise RuntimeError("private backup directory not secure")
    if info.st_uid != os.getuid():
        raise RuntimeError("private backup directory owner mismatch")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_exclusive(path, data):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def verify_pair(backup, manifest, source):
    binfo = require_regular(backup)
    minfo = require_regular(manifest)
    if (stat.S_IMODE(binfo.st_mode) != 0o600 or
            stat.S_IMODE(minfo.st_mode) != 0o600):
        raise RuntimeError("snapshot permissions not private")
    if binfo.st_size != len(source) or digest(backup.read_bytes()) != EXPECTED_SHA256:
        raise RuntimeError("snapshot preimage digest mismatch")
    record = json.loads(manifest.read_text("utf8"))
    if (record.get("source_sha256") != EXPECTED_SHA256 or
            record.get("bytes") != len(source) or
            record.get("scope") != "mpw_commerce/product_checkout_page.py" or
            record.get("release_permitted") is not False):
        raise RuntimeError("snapshot manifest mismatch")
    return True


def snapshot(root=ROOT, expected_owner="zomorod2"):
    if pwd.getpwuid(os.getuid()).pw_name != expected_owner:
        raise RuntimeError("unexpected cPanel user")
    app = root / "Saeit-staging"
    source = app / "mpw_commerce" / "product_checkout_page.py"
    wsgi = root / "mojplaywin.com" / "passenger_wsgi.py"
    private = root / ".private_mojplaywin_main_agents"
    for directory in (root, app, source.parent, wsgi.parent):
        if not stat.S_ISDIR(directory.lstat().st_mode):
            raise RuntimeError("unexpected parent directory")
    require_private_dir(private)
    require_regular(source)
    require_regular(wsgi)
    if WSGI_MARKER not in wsgi.read_text("utf8", "replace"):
        raise RuntimeError("Passenger application root marker changed")
    if source.stat().st_size > MAX_SOURCE:
        raise RuntimeError("checkout source unexpectedly large")
    original = source.read_bytes()
    if digest(original) != EXPECTED_SHA256:
        raise RuntimeError("checkout preimage SHA drift")
    fs = os.statvfs(private)
    if fs.f_bavail * fs.f_frsize < MIN_FREE:
        raise RuntimeError("local backup filesystem lacks headroom")
    backup = private / (STEM + ".bak")
    manifest = private / (STEM + ".json")
    directory_fd = os.open(private, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        fcntl.flock(directory_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if backup.exists() or manifest.exists() or backup.is_symlink() or manifest.is_symlink():
            verify_pair(backup, manifest, original)
            result = "EXISTING_VERIFIED"
        else:
            # Recheck under the same lock immediately before creating backup.
            if digest(source.read_bytes()) != EXPECTED_SHA256:
                raise RuntimeError("source changed during preimage snapshot")
            write_exclusive(backup, original)
            if digest(backup.read_bytes()) != EXPECTED_SHA256:
                raise RuntimeError("new preimage failed readback")
            record = {
                "scope": "mpw_commerce/product_checkout_page.py",
                "source_sha256": EXPECTED_SHA256,
                "bytes": len(original),
                "release_permitted": False,
                "independent_offhost_restore_verified": False,
                "passenger_db_authority_verified": False,
            }
            write_exclusive(manifest, (json.dumps(record, sort_keys=True) + "\n").encode())
            verify_pair(backup, manifest, original)
            result = "CREATED_AND_VERIFIED"
    finally:
        os.close(directory_fd)
    return {
        "scope": "S01_PRIVATE_PREIMAGE_ONLY",
        "result": result,
        "preimage_sha256": EXPECTED_SHA256,
        "backup_readback_verified": True,
        "app_source_modified": False,
        "database_modified": False,
        "orders_created": 0,
        "payments_created": 0,
        "offhost_restore_verified": False,
        "passenger_db_authority_verified": False,
        "release_permitted": False,
    }



def safe_failure_code(exc):
    """Classify a blocked snapshot without exposing private exception text."""
    if isinstance(exc, BlockingIOError):
        return "LOCK_BUSY"
    if isinstance(exc, RuntimeError):
        message = str(exc)
        rules = {
            "unexpected cPanel user": "OWNER_MISMATCH",
            "unexpected parent directory": "PARENT_TYPE_MISMATCH",
            "private backup directory not secure": "BACKUP_DIRECTORY_UNSAFE",
            "private backup directory owner mismatch": "BACKUP_DIRECTORY_OWNER_MISMATCH",
            "unexpected source/backup file type": "SOURCE_OR_BACKUP_TYPE_MISMATCH",
            "Passenger application root marker changed": "WSGI_ROOT_MISMATCH",
            "checkout source unexpectedly large": "SOURCE_SIZE_DRIFT",
            "checkout preimage SHA drift": "SOURCE_SHA_DRIFT",
            "local backup filesystem lacks headroom": "BACKUP_HEADROOM_LOW",
            "source changed during preimage snapshot": "SOURCE_CONCURRENT_DRIFT",
            "snapshot preimage digest mismatch": "EXISTING_BACKUP_CORRUPT",
            "snapshot permissions not private": "EXISTING_BACKUP_PERMISSIONS",
            "snapshot manifest mismatch": "EXISTING_MANIFEST_MISMATCH",
            "new preimage failed readback": "NEW_BACKUP_READBACK_FAILED",
        }
        return rules.get(message, "RUNTIME_GUARD_BLOCKED")
    if isinstance(exc, FileNotFoundError):
        return "REQUIRED_FILE_MISSING"
    if isinstance(exc, PermissionError):
        return "PERMISSION_DENIED"
    if isinstance(exc, json.JSONDecodeError):
        return "MANIFEST_JSON_INVALID"
    return "UNCLASSIFIED_BLOCKER"



if __name__ == "__main__":
    try:
        print("S01_PRIVATE_PREIMAGE=" + json.dumps(snapshot(), sort_keys=True))
    except (OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        print("S01_PRIVATE_PREIMAGE=" + json.dumps({
            "status": "BLOCKED_NO_SOURCE_CHANGE",
            "reason_code": safe_failure_code(exc),
            "release_permitted": False,
        }, sort_keys=True))
        raise SystemExit(1)
