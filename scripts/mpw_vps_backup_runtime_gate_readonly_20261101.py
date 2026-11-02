#!/usr/bin/env python3
"""Privacy-safe read-only VPS prerequisite probe for a NEW MojPlayWin archive.

Does not read recovery-key bytes, scan archives, copy SQL/files, create a key,
start GPG encryption, deploy, run Passenger, or alter any source.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import stat
from pathlib import Path

MIN_START_FREE = 10 * 1024**3
PARTIAL_NAME = re.compile(r"^mojplaywin_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{16}_(?:mysql|files)_gpgv2\.gpg\.partial$")


def private_directory(path: Path, uid: int) -> bool:
    try:
        info = path.lstat()
        return stat.S_ISDIR(info.st_mode) and info.st_uid == uid and not (info.st_mode & 0o077)
    except OSError:
        return False


def recovery_key_metadata_valid(path: Path, uid: int) -> bool:
    """Stat metadata only. Never open the key or calculate a key fingerprint."""
    try:
        info = path.lstat()
        return (stat.S_ISREG(info.st_mode) and info.st_uid == uid
                and not (info.st_mode & 0o177) and info.st_size == 32)
    except OSError:
        return False



def failed_partial_inventory(root: Path, uid: int) -> tuple[int, int, bool]:
    """Names and lstat only; never read archives or return private filenames."""
    if not private_directory(root, uid):
        return 0, 0, False
    count = total_bytes = 0
    try:
        for index, path in enumerate(root.iterdir()):
            if index >= 20_000:
                return count, total_bytes, True
            if not path.name.endswith(".gpg.partial"):
                continue
            info = path.lstat()
            if (not PARTIAL_NAME.fullmatch(path.name) or
                    not stat.S_ISREG(info.st_mode) or info.st_uid != uid):
                return count, total_bytes, True
            count += 1
            total_bytes += info.st_size
    except OSError:
        return count, total_bytes, True
    return count, total_bytes, False

def inspect(home: Path | None = None, *, free_bytes: int | None = None,
            uid: int | None = None, gpg_available: bool | None = None):
    home = Path.home() if home is None else Path(home)
    uid = os.geteuid() if uid is None else uid
    try:
        space = os.statvfs(home)
        measured = space.f_bavail * space.f_frsize
        free_measured = True
    except OSError:
        measured = 0
        free_measured = False
    if free_bytes is not None:
        measured = free_bytes
        free_measured = True
    if gpg_available is None:
        gpg_available = shutil.which("gpg") is not None
    root = home / ".private-mojplaywin-offhost-backups"
    secret_root = home / ".config" / "mojplaywin-backup-recovery"
    key = secret_root / "recovery-key.bin"
    storage = private_directory(root, uid)
    secret_parent = private_directory(secret_root, uid)
    key_ok = secret_parent and recovery_key_metadata_valid(key, uid)
    partial_count, partial_bytes, partial_unsafe = failed_partial_inventory(root, uid)
    capacity = free_measured and measured >= MIN_START_FREE
    return {
        "classification": "READ_ONLY_NEW_BACKUP_VPS_CAPACITY_AND_KEY",
        "vps_has_gpg_binary": bool(gpg_available),
        "free_capacity_meets_10gib_admission": bool(capacity),
        "private_backup_folder_exists_and_owner_only": storage,
        "failed_private_partial_count": partial_count,
        "failed_private_partial_bytes": partial_bytes,
        "failed_private_partial_metadata_unsafe": partial_unsafe,
        "existing_recovery_key_metadata_owner_only_32_bytes": bool(key_ok),
        "owner_armed_backup_runtime_prerequisites_ready": bool(
            capacity and gpg_available and key_ok and (storage or not root.exists())
            and partial_count == 0 and not partial_unsafe),
        "recovery_key_bytes_read": False,
        "key_exported_off_vps": False,
        "archive_bytes_read": False,
        "archive_created": False,
        "source_modified": False,
        "orders_created": 0,
        "payments_created": 0,
        "release_permitted": False,
    }


if __name__ == "__main__":
    report = inspect()
    print("MPW_VPS_BACKUP_RUNTIME_PREFLIGHT=" + json.dumps(report, sort_keys=True))
    if sys.argv[1:] == ["--require-ready"]:
        raise SystemExit(0 if report["owner_armed_backup_runtime_prerequisites_ready"] else 1)
    if sys.argv[1:]:
        raise SystemExit(2)
