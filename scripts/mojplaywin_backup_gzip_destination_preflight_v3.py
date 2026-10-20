#!/usr/bin/env python3
"""Fail-closed, read-only VPS destination preflight for dated GPG backup pair.

This must run before the privileged primary transfer. It does not create,
delete, or read archives/keys; only securely stats fixed target paths and
checks space and directory ownership. Never approves public release.
"""
from __future__ import annotations
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

MIN_FREE = 10 * 1024**3
MODES = ("mysql", "files")


def private_dir(path):
    try:
        if path.is_symlink():
            return False
        s = path.stat()
        return (stat.S_ISDIR(s.st_mode) and s.st_uid == os.getuid()
                and not (s.st_mode & 0o077))
    except OSError:
        return False


def private_key(path):
    try:
        if path.is_symlink():
            return False
        s = path.stat()
        return (stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid()
                and s.st_size == 32 and not (s.st_mode & 0o177))
    except OSError:
        return False


def check(date, *, home=None, min_free=MIN_FREE):
    if not isinstance(date, str) or not re.fullmatch(r"20\d{6}", date):
        raise ValueError("unsafe version date")
    if min_free < 0:
        raise ValueError("invalid threshold")
    home = Path.home() if home is None else Path(home)
    backup = home / ".private-mojplaywin-offhost-backups"
    config = home / ".config" / "mojplaywin-backup-recovery"
    key = config / "recovery-key.bin"
    gpg_home = config / "gnupg-v2"
    dirs_private = all(private_dir(x) for x in (backup, config, gpg_home))
    key_safe = private_key(key)
    names_clear = all(
        not p.exists() and not p.is_symlink()
        for kind in MODES
        for ext in (".gpg", ".gpg.partial", ".manifest.json")
        for p in (backup / (f"mojplaywin_{date}_{kind}_gpgv2" + ext),)
    )
    free = shutil.disk_usage(backup).free if dirs_private else 0
    result = {
        "classification": "PRIVATE_VPS_BACKUP_DESTINATION_PREFLIGHT",
        "private_directories": dirs_private,
        "existing_recovery_key_private": key_safe,
        "new_version_output_names_free": names_clear,
        "at_least_10_gib_free": free >= min_free,
        "gpg_available": shutil.which("gpg") is not None,
        "isolated_restore_verified": False,
        "release_permitted": False,
    }
    result["safe_to_begin_scoped_backup"] = (
        result["private_directories"] and result["existing_recovery_key_private"]
        and result["new_version_output_names_free"] and result["at_least_10_gib_free"]
        and result["gpg_available"]
    )
    return result


def main():
    if len(sys.argv) != 2:
        raise SystemExit(2)
    try:
        result = check(sys.argv[1])
        print(json.dumps(result, sort_keys=True))
        raise SystemExit(0 if result["safe_to_begin_scoped_backup"] else 1)
    except (OSError, ValueError):
        print(json.dumps({
            "classification": "PRIVATE_VPS_BACKUP_DESTINATION_PREFLIGHT",
            "safe_to_begin_scoped_backup": False,
            "isolated_restore_verified": False,
            "release_permitted": False,
        }, sort_keys=True))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
