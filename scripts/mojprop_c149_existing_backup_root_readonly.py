#!/usr/bin/env python3
"""C149 read-only metadata inventory of exactly ONE owner Plan1 backup root.

Do not open files, backups, manifest contents or DB snapshots. No recursion;
only bounded first-level owner-private subdirectories and fixed manifest
metadata names. Never show entry names, dates, customer records, secrets,
paths, filenames, tokens or archive contents. A candidate is NOT a verified
backup, restore or sufficient recovery capacity.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import re
import stat

OWNER = "zomorod2"
BACKUP_ROOT = Path("/home/zomorod2/.mojplaywin-moj-prop-backups")
MAX_ENTRIES = 128
MAX_CHILDREN = 64
MAX_FILE_BYTES = 40 * 1024 * 1024 * 1024
RUN_ID = re.compile(r"(?:[0-9]{8,20}|mojprop[-_][a-z0-9_-]{4,45})\Z")
ARCHIVE_SUFFIX = (".tar.gz", ".tgz", ".tar", ".zip", ".sql.gz", ".gz")
FIXED_MANIFESTS = ("manifest.json", "backup-manifest.json",
                   "predeploy-manifest.json", "isolated-restore-evidence.json")


def owned_private(path: Path, uid: int, *, directory: bool) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    if info.st_uid != uid or info.st_mode & 0o022:
        return False
    if directory:
        return stat.S_ISDIR(info.st_mode)
    return (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
            and 0 < info.st_size <= MAX_FILE_BYTES)


def scan_fixed_backup_root(root: Path, uid: int) -> dict:
    out = {"scan_completed": False, "root_safe": False,
           "direct_entries_scanned": 0,
           "owner_private_subdirectories": 0,
           "owner_private_regular_archives": 0,
           "owner_private_manifest_metadata_files": 0,
           "matched_run_dirs_with_manifest_metadata": 0,
           "metadata_only": True, "backup_content_read": False,
           "restore_rehearsal_verified": False,
           "independent_full_app_db_media_restore_proven": False}
    if not owned_private(root,uid,directory=True):
        return out
    out["root_safe"] = True
    dirs = 0
    archives = 0
    manifest_count = 0
    reviewed_dirs = 0
    count = 0
    try:
        with os.scandir(root) as entries:
            for item in entries:
                count += 1
                if count > MAX_ENTRIES:
                    return out
                try:
                    meta = item.stat(follow_symlinks=False)
                except OSError:
                    continue
                if meta.st_uid != uid or meta.st_mode & 0o022:
                    continue
                if stat.S_ISDIR(meta.st_mode):
                    dirs += 1
                    if dirs > MAX_CHILDREN:
                        return out
                    if not RUN_ID.fullmatch(item.name):
                        continue
                    # Never iterate or read the subdir; only lstat fixed names.
                    manifests = sum(
                        1 for name in FIXED_MANIFESTS
                        if owned_private(root / item.name / name, uid,
                                         directory=False)
                    )
                    if manifests:
                        reviewed_dirs += 1
                        manifest_count += manifests
                elif (stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1
                      and 0 < meta.st_size <= MAX_FILE_BYTES):
                    if item.name in FIXED_MANIFESTS:
                        manifest_count += 1
                    elif item.name.lower().endswith(ARCHIVE_SUFFIX):
                        archives += 1
        out.update(scan_completed=True, direct_entries_scanned=count,
                   owner_private_subdirectories=dirs,
                   owner_private_regular_archives=archives,
                   owner_private_manifest_metadata_files=manifest_count,
                   matched_run_dirs_with_manifest_metadata=reviewed_dirs)
    except OSError:
        pass
    return out


def report() -> dict:
    out = {
        "schema": "mojprop.cpanel.existing_backup_root.metadata.c149.v1",
        "owner_identity_verified": False, "read_only": True,
        "inventory": scan_fixed_backup_root(Path("/no-such-root-for-safe-default"), -1),
        "provider_offhost_backup_proven": False,
        "offhost_capacity_proven": False,
        "database_restore_verified": False,
        "application_restore_verified": False,
        "media_restore_verified": False,
        "tenant_quota_verified": False,
        "customer_data_accessed": False,
        "backup_downloaded_or_created": False,
        "database_accessed": False,
        "external_network_called": False,
        "production_release_authorized": False,
        "cost_incurred": False,
    }
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != OWNER:
            return out
        out["owner_identity_verified"] = True
        out["inventory"] = scan_fixed_backup_root(BACKUP_ROOT, os.geteuid())
    except (OSError, ValueError, KeyError):
        pass
    return out


if __name__ == "__main__":
    print("MOJPROP_C149_BACKUP_ROOT_METADATA_READONLY=" +
          json.dumps(report(), sort_keys=True, separators=(",", ":")))
