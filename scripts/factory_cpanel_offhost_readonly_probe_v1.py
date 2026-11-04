#!/usr/bin/env python3
"""Read-only suitability preflight for a proposed cPanel factory backup vault.

This command never creates directories, writes backups, installs credentials,
or authorizes a transfer. A successful capacity check is NOT an off-host
recovery attestation. No user-controlled paths other than the fixed private
candidate under the account home are evaluated.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess


SCHEMA = "saeit.factory.cpanel-offhost-suitability.v1"
CANDIDATE_NAME = ".saeit-factory-offhost"
MIB = 1024 * 1024


def _quota_mib(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("CPANEL_QUOTA_VALUE_INVALID")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("CPANEL_QUOTA_VALUE_INVALID") from None
    if not number.is_finite() or number < 0:
        raise ValueError("CPANEL_QUOTA_VALUE_INVALID")
    return number


def _read_cpanel_quota() -> tuple[int, int]:
    command = subprocess.run(
        ["uapi", "--output=json", "Quota", "get_quota_info"],
        capture_output=True, text=True, timeout=25, check=False,
    )
    if command.returncode:
        raise ValueError("CPANEL_QUOTA_UAPI_FAILED")
    try:
        response = json.loads(command.stdout)
        block = response["result"]["data"]
        if not isinstance(block, dict):
            raise KeyError("data")
        used = _quota_mib(block["megabytes_used"])
        limit = _quota_mib(block["megabyte_limit"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("CPANEL_QUOTA_UNTRUSTWORTHY") from exc
    if limit <= 0 or used > limit:
        raise ValueError("CPANEL_QUOTA_UNTRUSTWORTHY")
    return int(used * MIB), int(limit * MIB)


def _has_symlink_component(path: Path) -> bool:
    return any(part.is_symlink() for part in (path, *path.parents))


def _private_location_check(home: Path, uid: int) -> tuple[bool, str]:
    candidate = home / CANDIDATE_NAME
    if _has_symlink_component(candidate):
        return False, "CPANEL_VAULT_SYMLINK_PATH"
    try:
        base = home.stat()
        vault = candidate.stat()
    except FileNotFoundError:
        return False, "CPANEL_VAULT_MISSING"
    except OSError:
        return False, "CPANEL_VAULT_UNREADABLE"
    if not stat.S_ISDIR(base.st_mode) or not stat.S_ISDIR(vault.st_mode):
        return False, "CPANEL_VAULT_NOT_DIRECTORY"
    if base.st_uid != uid or vault.st_uid != uid:
        return False, "CPANEL_VAULT_OWNER_MISMATCH"
    if base.st_mode & 0o022 or vault.st_mode & 0o077:
        return False, "CPANEL_VAULT_PERMISSIONS_UNSAFE"
    return True, "CPANEL_PRIVATE_VAULT_CANDIDATE"


def inspect(
    home: Path,
    *,
    checkpoint_cap_mib: int = 512,
    reserve_mib: int = 1024,
    uid: int | None = None,
    quota_bytes: tuple[int, int] | None = None,
    disk_free_bytes: int | None = None,
) -> dict:
    if not 1 <= checkpoint_cap_mib <= 4096 or not 512 <= reserve_mib <= 16384:
        raise ValueError("CPANEL_UNSAFE_CAPACITY_ARGUMENT")
    if uid is None:
        uid = os.getuid()
    vault_ok, vault_reason = _private_location_check(home, uid)
    quota_ok = False
    account_headroom = None
    quota_reason = "CPANEL_QUOTA_NOT_VERIFIED"
    if quota_bytes is None:
        try:
            quota_bytes = _read_cpanel_quota()
        except (ValueError, OSError, subprocess.TimeoutExpired):
            quota_bytes = None
    if quota_bytes is not None:
        used, limit = quota_bytes
        if 0 <= used <= limit and limit > 0:
            account_headroom = limit - used
            quota_ok = True
            quota_reason = "CPANEL_QUOTA_MEASURED"
    if disk_free_bytes is None:
        try:
            disk_free_bytes = shutil.disk_usage(home).free
        except OSError:
            disk_free_bytes = None
    mount_ok = isinstance(disk_free_bytes, int) and disk_free_bytes >= 0
    # Bound for a ciphertext copy plus a temporary reconstruction and margin;
    # actual plaintext expansion must be checked separately before any transfer.
    requirement = (3 * checkpoint_cap_mib + reserve_mib) * MIB
    capacity_ok = bool(
        quota_ok and mount_ok and account_headroom >= requirement
        and disk_free_bytes >= requirement
    )
    return {
        "schema": SCHEMA,
        "inspection": "read_only",
        "status": "HOLD_NO_TRANSFER_AUTHORIZED",
        "vault": vault_reason,
        "vault_candidate_private": vault_ok,
        "quota": quota_reason,
        "quota_headroom_bytes": account_headroom,
        "filesystem_free_bytes": disk_free_bytes if mount_ok else None,
        "required_headroom_bytes": requirement,
        "capacity_candidate_pass": capacity_ok,
        "at_rest_encryption_verified": False,
        "independent_restore_verified": False,
        "independent_receipt_signature_verified": False,
        "transfer_authorized": False,
        "live_mutations": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-cap-mib", type=int, default=512)
    parser.add_argument("--reserve-mib", type=int, default=1024)
    args = parser.parse_args()
    result = inspect(
        Path.home(), checkpoint_cap_mib=args.checkpoint_cap_mib,
        reserve_mib=args.reserve_mib,
    )
    print("F01_CPANEL_OFFHOST_READ_ONLY=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
