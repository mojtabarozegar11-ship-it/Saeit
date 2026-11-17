#!/usr/bin/env python3
"""Owner cPanel home directory archive *metadata only*, never a restore.

This is a secondary no-cost local locator when Backup UAPI is inaccessible.
No recursion, contents, backups, file hashes, downloads, SQL, credentials,
restores, user input or arbitrary directory scans. Results have NO filenames.
A local backup candidate is neither complete nor independently restorable.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import re
import stat

ACCOUNT = "zomorod2"
HOME = Path("/home/zomorod2")
MAX_ENTRIES = 2048
# Standard user-generated tarballs, never a wildcard containing other users.
BACKUP_NAME = re.compile(
    r"backup-[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4}_[0-9]{1,2}-[0-9]{1,2}-[0-9]{1,2}_zomorod2\.tar\.gz\Z"
)
MIN_ARCHIVE_BYTES = 1024


def scan_fixed_home_metadata(home: Path, *, uid: int) -> dict:
    result = {
        "home_metadata_scan_completed": False,
        "local_archive_candidates_count": 0,
        "safe_owner_regular_file_metadata": False,
    }
    try:
        info = home.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != uid
                or info.st_mode & 0o022):
            return result
        scanned = 0
        found = 0
        with os.scandir(home) as entries:
            for entry in entries:
                scanned += 1
                if scanned > MAX_ENTRIES:
                    # A truncated scan cannot prove absence of a backup.
                    return result
                if BACKUP_NAME.fullmatch(entry.name) is None:
                    continue
                meta = entry.stat(follow_symlinks=False)
                if (stat.S_ISREG(meta.st_mode) and meta.st_uid == uid
                        and meta.st_nlink == 1 and not (meta.st_mode & 0o077)
                        and MIN_ARCHIVE_BYTES <= meta.st_size <= 10_000_000_000):
                    found += 1
        result["home_metadata_scan_completed"] = True
        result["local_archive_candidates_count"] = found
        result["safe_owner_regular_file_metadata"] = found > 0
    except (OSError, ValueError, PermissionError):
        pass
    return result


def inspect() -> dict:
    output = {
        "schema": "mojprop.owner_local_archive_metadata.readonly.c120.v1",
        "read_only": True,
        "owner_identity_verified": False,
        "home_metadata_scan_completed": False,
        "local_archive_candidates_count": 0,
        "safe_owner_regular_file_metadata": False,
        "local_archive_content_read": False,
        "archive_downloaded": False,
        "app_or_db_accessed": False,
        "customer_data_accessed": False,
        "independent_encrypted_full_restore_proven": False,
        "provider_offhost_backup_verified": False,
        "production_deployment_authorized": False,
        "new_cost_incurred": False,
    }
    try:
        uid = os.geteuid()
        if pwd.getpwuid(uid).pw_name != ACCOUNT:
            return output
        output["owner_identity_verified"] = True
        output.update(scan_fixed_home_metadata(HOME, uid=uid))
    except (OSError, KeyError, ValueError):
        pass
    return output


if __name__ == "__main__":
    print("MOJPROP_C120_LOCAL_ARCHIVE_METADATA_READONLY=" +
          json.dumps(inspect(), sort_keys=True, separators=(",", ":")))
