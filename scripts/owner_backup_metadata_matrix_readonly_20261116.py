#!/usr/bin/env python3
"""Owner-only storage recovery metadata, with no backup contents read or writes.

Outputs aggregate bands only. A discovered backup is NOT proof of recoverability.
"""
import json
import os
import pwd
import stat
import sys
import time
from pathlib import Path

CAP_FILES = 30000
CAP_DEPTH = 9
CAP_RUNTIME_SECONDS = 60
NOW = time.time()
START = time.monotonic()


def band(n):
    if n == 0:
        return "0"
    for x in (1, 5, 20, 100, 500, 2000, 10000, 30000):
        if n <= x:
            return "<=" + str(x)
    return ">30000"


def size_band(n):
    if n == 0:
        return "0"
    mib = (n + 1048575) // 1048576
    for x in (1, 10, 64, 256, 1024, 4096, 8192, 16384):
        if mib <= x:
            return "<=" + str(x) + " MiB"
    return ">16384 MiB"


def inspect(path, uid, home_device):
    result = {"status": "not_present", "files_band": "0",
              "logical_size_band": "0", "oldest_age_days_band": "none",
              "newest_age_days_band": "none", "symlinks": False,
              "foreign_or_mounted": False, "hardlinks": False,
              "scan_complete": False, "any_sqlite_files": False,
              "any_archive_files": False, "contains_db_and_media_proven": False,
              "integrity_hash_proven": False, "independent_restore_proven": False}
    try:
        root = path.lstat()
    except FileNotFoundError:
        result["scan_complete"] = True
        return result
    if not stat.S_ISDIR(root.st_mode) or root.st_uid != uid or root.st_dev != home_device:
        result["status"] = "unsafe_root"
        return result
    result["status"] = "present"
    files = 0
    logical_bytes = 0
    min_age = 10**8
    max_age = 0
    incomplete = False
    stack = [(path, 0)]
    while stack:
        if time.monotonic() - START > CAP_RUNTIME_SECONDS:
            incomplete = True
            break
        directory, depth = stack.pop()
        if depth > CAP_DEPTH:
            incomplete = True
            break
        try:
            children = list(directory.iterdir())
        except OSError:
            incomplete = True
            break
        for child in children:
            if files >= CAP_FILES:
                incomplete = True
                break
            try:
                s = child.lstat()
            except OSError:
                incomplete = True
                continue
            if stat.S_ISLNK(s.st_mode):
                result["symlinks"] = True
                continue
            if s.st_uid != uid or s.st_dev != home_device:
                result["foreign_or_mounted"] = True
                continue
            if stat.S_ISDIR(s.st_mode):
                stack.append((child, depth + 1))
                continue
            if not stat.S_ISREG(s.st_mode):
                incomplete = True
                continue
            files += 1
            logical_bytes += s.st_size
            age = max(0, int((NOW - s.st_mtime) // 86400))
            min_age = min(min_age, age)
            max_age = max(max_age, age)
            result["hardlinks"] |= s.st_nlink > 1
            result["any_sqlite_files"] |= child.suffix.lower() in (".sqlite", ".sqlite3", ".db")
            result["any_archive_files"] |= child.suffix.lower() in (".gz", ".tgz", ".zip", ".zst", ".xz", ".tar", ".sql", ".bak", ".gpg")
        if incomplete:
            break
    result["files_band"] = band(files)
    result["logical_size_band"] = size_band(logical_bytes)
    result["oldest_age_days_band"] = "0-7" if max_age <= 7 else "8-30" if max_age <= 30 else "31-90" if max_age <= 90 else ">90"
    result["newest_age_days_band"] = "0-7" if min_age <= 7 else "8-30" if min_age <= 30 else "31-90" if min_age <= 90 else ">90"
    if files == 0:
        result["oldest_age_days_band"] = result["newest_age_days_band"] = "none"
    result["scan_complete"] = not incomplete
    return result


def probe(mode):
    if mode == "cpanel":
        home = Path("/home/zomorod2")
        owner = "zomorod2"
        targets = {"store_archive": home / ".mojplaywin-backups",
                   "prop_archive": home / ".mojplaywin-moj-prop-backups",
                   "starter_archive": home / ".mojprop-starter30-backups"}
        active_app = home / "Saeit-staging" / "manage.py"
    elif mode == "vps":
        home = Path("/home/githubops")
        owner = "githubops"
        targets = {"factory_backup_root": home / "factory-runtime/operations/backups"}
        active_app = home / "factory-runtime/operations"
    else:
        raise RuntimeError("INVALID_MODE")
    if pwd.getpwuid(os.geteuid()).pw_name != owner:
        raise RuntimeError("OWNER_MISMATCH")
    st = home.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or active_app.is_symlink() or not active_app.exists():
        raise RuntimeError("OWNER_APP_MISMATCH")
    out = {label: inspect(path, os.geteuid(), st.st_dev) for label, path in targets.items()}
    return {"schema": "owner.storage.backup_metadata.readonly.v1", "role": mode,
            "backups": out,
            "backup_contents_read": False,
            "files_created_modified_or_deleted": False,
            "restore_executed": False,
            "backup_usable_for_production_recovery_proven": False,
            "production_release_authorized": False,
            "new_costs": False}


if __name__ == "__main__":
    try:
        report = probe(sys.argv[1] if len(sys.argv) == 2 else None)
        print("OWNER_BACKUP_METADATA=" + json.dumps(report, sort_keys=True, separators=(",", ":")))
    except Exception as exc:
        print("OWNER_BACKUP_METADATA_BLOCKED=" + type(exc).__name__)
        raise SystemExit(1)
