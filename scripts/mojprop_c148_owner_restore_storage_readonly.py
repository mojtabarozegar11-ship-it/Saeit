#!/usr/bin/env python3
"""C148 cPanel owner-owned backup-capacity and Plan1 ownership metadata only.

Fixed account paths and bounded top-level directory entries. NEVER open DB,
customer records, backup contents, evidence receipts or credentials; no shell,
network, database, deploy, migration, chmod, backup or archive creation.
Filesystem availability is NOT independent restore capacity or account quota.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import re
import stat

OWNER = "zomorod2"
HOME = Path("/home/zomorod2")
STAGING = HOME / "Saeit-staging"
WEBROOT = HOME / "mojplaywin.com"
PROPDIR = STAGING / "prop_firm"
LEAD = PROPDIR / "lead_models.py"
BACKUPDIR = HOME / ".mojplaywin-moj-prop-backups"
EVIDENCEDIR = HOME / ".mojprop-private-db-restore-evidence"
MAX_ENTRIES = 128
RESTORE_CASE = re.compile(r"mojprop_restore_[a-z0-9_]{8,60}\Z")


def classify_path(path: Path, owner_uid: int, *, file: bool) -> str:
    """lstat only; reject symlinks, wrong ownership, hard links and writable paths."""
    try:
        meta = path.lstat()
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unavailable"
    if stat.S_ISLNK(meta.st_mode):
        return "symlink"
    if meta.st_uid != owner_uid:
        return "wrong_owner"
    if meta.st_mode & 0o002:
        return "world_writable"
    if meta.st_mode & 0o020:
        return "group_writable"
    if file:
        if not stat.S_ISREG(meta.st_mode):
            return "not_regular_file"
        if meta.st_nlink != 1:
            return "hardlinked"
    elif not stat.S_ISDIR(meta.st_mode):
        return "not_directory"
    return "safe"


def normalized_disk_usage(path: Path) -> dict:
    """Only aggregate disk availability; never infer plan quota or restore size."""
    out = {"measured": False, "available_mib_floor": None,
           "total_mib_floor": None, "available_inodes": None,
           "account_quota_free_bytes_verified": False,
           "independent_offhost_restore_space_verified": False}
    try:
        stats = os.statvfs(path)
        available = stats.f_bavail * stats.f_frsize
        total = stats.f_blocks * stats.f_frsize
        if available < 0 or total <= 0 or available > total:
            return out
        out.update(measured=True, available_mib_floor=available // 1048576,
                   total_mib_floor=total // 1048576,
                   available_inodes=(stats.f_favail if stats.f_favail >= 0 else None))
    except OSError:
        pass
    return out


def count_private_restore_cases(root: Path, owner_uid: int) -> dict:
    """Direct child directory metadata only; do not open or attest any receipt."""
    out = {"bounded_scan_completed": False, "matching_owner_private_case_dirs": 0,
           "read_any_receipt_or_backup": False, "independent_restore_proven": False}
    if classify_path(root, owner_uid, file=False) != "safe":
        return out
    total = 0
    try:
        with os.scandir(root) as entries:
            for number, entry in enumerate(entries, 1):
                if number > MAX_ENTRIES:
                    return out
                if not RESTORE_CASE.fullmatch(entry.name):
                    continue
                try:
                    # No-follow lstat; no directory traversal and no content read.
                    info = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if (stat.S_ISDIR(info.st_mode) and info.st_uid == owner_uid
                        and not (info.st_mode & 0o077)):
                    total += 1
    except OSError:
        return out
    out["bounded_scan_completed"] = True
    out["matching_owner_private_case_dirs"] = total
    return out


def report() -> dict:
    result = {
        "schema": "mojprop.owner.cpanel.disk_restore_metadata.readonly.c148.v1",
        "read_only": True,
        "owner_identity_verified": False,
        "fixed_path_states": {name: "unavailable" for name in (
            "home", "staging", "webroot", "prop_firm_dir",
            "prop_interest_model_file", "local_plan1_backup_dir",
            "independent_restore_evidence_dir")},
        "prop_interest_model_chain_safe": False,
        "storage": normalized_disk_usage(Path("/definitely-no-disk-access-placeholder")),
        "case_metadata": {
            "bounded_scan_completed": False,
            "matching_owner_private_case_dirs": 0,
            "read_any_receipt_or_backup": False,
            "independent_restore_proven": False,
        },
        "account_quota_verified": False,
        "offhost_backup_verified": False,
        "full_app_db_media_restore_verified": False,
        "customer_data_accessed": False,
        "backup_content_read": False,
        "database_accessed": False,
        "external_network_called": False,
        "payment_created": False,
        "production_deployment_authorized": False,
        "cost_incurred": False,
    }
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != OWNER:
            return result
        result["owner_identity_verified"] = True
        fixed = (
            ("home", HOME, False),
            ("staging", STAGING, False),
            ("webroot", WEBROOT, False),
            ("prop_firm_dir", PROPDIR, False),
            ("prop_interest_model_file", LEAD, True),
            ("local_plan1_backup_dir", BACKUPDIR, False),
            ("independent_restore_evidence_dir", EVIDENCEDIR, False),
        )
        result["fixed_path_states"] = {
            label: classify_path(path, os.geteuid(), file=is_file)
            for label, path, is_file in fixed
        }
        states = result["fixed_path_states"]
        result["prop_interest_model_chain_safe"] = all(
            states[name] == "safe" for name in (
                "home", "staging", "prop_firm_dir", "prop_interest_model_file")
        )
        if states["staging"] == "safe":
            result["storage"] = normalized_disk_usage(STAGING)
        if states["independent_restore_evidence_dir"] == "safe":
            result["case_metadata"] = count_private_restore_cases(
                EVIDENCEDIR, os.geteuid())
    except (OSError, ValueError, KeyError):
        pass
    return result


if __name__ == "__main__":
    print("MOJPROP_C148_OWNER_DISK_RESTORE_READONLY=" +
          json.dumps(report(), sort_keys=True, separators=(",", ":")))
