#!/usr/bin/env python3
"""Owner-only zero-write proof of *capacity*, not of a successful DB restore.

Inspect the actual cPanel MariaDB size estimate, OS free space and tenant quota
before any proposed full Moj Prop site backup. Never creates a snapshot,
touches production data, logs database names, uploads files or claims readiness.
"""
from __future__ import annotations
import json
import os
import pwd
import stat
import sys
from pathlib import Path

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
PUBLIC = HOME / "mojplaywin.com"
RESTORE_EVIDENCE = HOME / ".mojprop-private-db-restore-evidence"
ACCOUNT = "zomorod2"
HEADROOM = 256 * 1024 * 1024
MAX_REASONABLE_DB_ESTIMATE = 100 * 1024**4


def capacity_flags(*, free_bytes, db_bytes, quota_accepted):
    """Conservative heuristic only: actual dump/media/restore can need more."""
    known = (type(free_bytes) is int and free_bytes >= 0
             and type(db_bytes) is int and 0 < db_bytes <= MAX_REASONABLE_DB_ESTIMATE)
    enough = free_bytes >= 2 * db_bytes + HEADROOM if known else None
    return {
        "connected_db_table_size_estimate_available": (
            type(db_bytes) is int and 0 < db_bytes <= MAX_REASONABLE_DB_ESTIMATE
        ),
        "filesystem_capacity_heuristic_passed": enough,
        "tenant_quota_proven_for_2x_db_estimate": quota_accepted is True if known else False,
        "combined_capacity_preflight_passed": (
            enough is True and quota_accepted is True
        ),
        "full_database_dump_taken": False,
        "isolated_database_restore_executed": False,
        "media_and_app_recovery_proven": False,
        "passenger_tenant_isolation_proven": False,
        "production_deployment_authorized": False,
        "customer_payment_collected_by_probe": False,
    }


def private_proof_folder_present():
    """Existence is informative; never mistake for independently signed proof."""
    try:
        s = RESTORE_EVIDENCE.lstat()
        return (stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode)
                and s.st_uid == os.geteuid() and s.st_mode & 0o077 == 0)
    except OSError:
        return False


def _select_db_estimate():
    from django.db import connection
    if connection.vendor != "mysql":
        raise ValueError("unsupported database engine")
    connection.ensure_connection()  # Django's initial session SET, *before* SELECT guard.
    def select_only(execute, sql, params, many, context):
        words = sql.lstrip().upper().split(None, 1) if type(sql) is str else []
        if not words or words[0] != "SELECT":
            raise PermissionError("non-SELECT business query blocked")
        return execute(sql, params, many, context)
    with connection.execute_wrapper(select_only):
        with connection.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(DATA_LENGTH + INDEX_LENGTH), 0) "
                "FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()"
            )
            value = cur.fetchone()[0]
    return int(value)


def _quota_result(needed_bytes):
    """Return only a bounded outcome code; never expose raw quota or paths."""
    import subprocess
    try:
        fd = os.open(HOME, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            stats = os.fstatvfs(fd)
            if (stats.f_bavail * stats.f_frsize < needed_bytes + 64 * 1024 * 1024
                    or stats.f_favail < 32):
                return False, "filesystem_reserve_failed"
        finally:
            os.close(fd)
    except OSError:
        return False, "filesystem_probe_failed"
    try:
        proc = subprocess.run(
            ["quota", "-wvu", ACCOUNT], timeout=6, check=True,
            capture_output=True, text=True,
            env={"LC_ALL": "C", "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
    except FileNotFoundError:
        return False, "quota_program_unavailable"
    except subprocess.TimeoutExpired:
        return False, "quota_program_timeout"
    except (OSError, subprocess.SubprocessError):
        return False, "quota_program_failed"
    saw_volume = False
    for line in proc.stdout.splitlines():
        fields = line.split()
        if not fields or not fields[0].startswith("/dev/"):
            continue
        if len(fields) != 7 or any(not x.isdecimal() for x in fields[1:]):
            return False, "quota_format_unrecognized"
        used_kib, soft_kib, hard_kib, inode_used, inode_soft, inode_hard = (
            int(x) for x in fields[1:]
        )
        used, soft, hard = used_kib * 1024, soft_kib * 1024, hard_kib * 1024
        if any(limit and limit - used < needed_bytes + 64 * 1024 * 1024
               for limit in (soft, hard)):
            return False, "quota_blocks_insufficient"
        if any(limit and limit - inode_used < 32
               for limit in (inode_soft, inode_hard)):
            return False, "quota_inodes_insufficient"
        saw_volume = True
    return (True, "quota_exact_verified") if saw_volume else (
        False, "quota_volume_not_reported"
    )


def _quota_checked(needed_bytes):
    return _quota_result(needed_bytes)[0]


def _cpanel_quota_data_adequate(document, needed_bytes):
    """Use fixed cPanel UAPI fields only; do not trust unlimited/disabled as proof."""
    from decimal import Decimal, InvalidOperation
    if (type(document) is not dict
            or type(document.get("result")) is not dict
            or document["result"].get("status") != 1
            or type(document["result"].get("data")) is not dict):
        return False, "cpanel_uapi_invalid_response"
    data = document["result"]["data"]
    if any(type(data.get(k)) is not int or data[k] != 1
           for k in ("under_quota_overall", "under_megabyte_limit",
                     "under_inode_limit")):
        return False, "cpanel_uapi_limit_exceeded_or_unknown"
    try:
        def number(field):
            value = data[field]
            if type(value) not in (int, float, str):
                raise ValueError(field)
            out = Decimal(str(value))
            if not out.is_finite() or out < 0:
                raise ValueError(field)
            return out
        limit_mb = number("megabyte_limit")
        remain_mb = number("megabytes_remain")
        inode_limit = data["inode_limit"]
        inodes_remain = data["inodes_remain"]
        if (type(inode_limit) is not int or inode_limit < 0
                or type(inodes_remain) is not int or inodes_remain < 0):
            raise ValueError("inode")
    except (KeyError, ValueError, InvalidOperation, TypeError):
        return False, "cpanel_uapi_invalid_quantities"
    if limit_mb == 0:
        return False, "cpanel_uapi_unlimited_or_disabled_unproven"
    # One decimal MB is conservatively 1,000,000 bytes, not MiB.
    if remain_mb * Decimal(1_000_000) < Decimal(needed_bytes + 64 * 1024 * 1024):
        return False, "cpanel_uapi_quota_bytes_insufficient"
    if inode_limit and inodes_remain < 32:
        return False, "cpanel_uapi_quota_inodes_insufficient"
    return True, "cpanel_uapi_quota_verified"


def _cpanel_uapi_quota_result(needed_bytes):
    """Official owner-only read-only UAPI: explicit user, then same-user CLI."""
    import subprocess
    binary = "/usr/local/cpanel/bin/uapi"
    variants = (
        [binary, "--output=json", "--user=" + ACCOUNT,
         "Quota", "get_quota_info"],
        [binary, "--output=json", "Quota", "get_quota_info"],
    )
    proc = None
    for fixed_args in variants:
        try:
            proc = subprocess.run(
                fixed_args, check=True, timeout=12, capture_output=True,
                text=True, env={"LC_ALL": "C",
                                "PATH": "/usr/bin:/bin:/usr/local/bin"},
            )
            break
        except FileNotFoundError:
            return False, "cpanel_uapi_program_unavailable"
        except subprocess.TimeoutExpired:
            return False, "cpanel_uapi_timeout"
        except (OSError, subprocess.SubprocessError):
            proc = None
            continue
    if proc is None:
        return False, "cpanel_uapi_both_owner_modes_failed"
    if len(proc.stdout) > 16384:
        return False, "cpanel_uapi_response_oversize"
    try:
        parsed = json.loads(proc.stdout)
    except (ValueError, TypeError):
        return False, "cpanel_uapi_unparseable"
    return _cpanel_quota_data_adequate(parsed, needed_bytes)

def main():
    out = {
        "schema": "mojprop.full_restore.capacity_readonly.v1",
        "read_only": True,
        "owner_identity_verified": False,
        "expected_app_and_public_roots_verified": False,
        "private_restore_folder_present_unverified": False,
        "database_probe_available": False,
        "quota_probe_available": False,
        "no_host_or_database_writes": True,
    }
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != ACCOUNT:
            raise ValueError("wrong owner")
        out["owner_identity_verified"] = True
        if any(path.is_symlink() or not path.is_dir() for path in (HOME, APP, PUBLIC)):
            raise ValueError("unverified root")
        out["expected_app_and_public_roots_verified"] = True
        out["private_restore_folder_present_unverified"] = private_proof_folder_present()
        os.chdir(APP)
        sys.path.insert(0, str(APP))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        import django
        django.setup()
        db_bytes = _select_db_estimate()
        out["database_probe_available"] = True
        fs = os.statvfs(HOME)
        free = int(fs.f_bavail) * int(fs.f_frsize)
        requirement = 2 * db_bytes + HEADROOM if 0 < db_bytes <= MAX_REASONABLE_DB_ESTIMATE else 0
        # Failure to prove the quota is UNKNOWN, not automatically 'no space'.
        quota, reason = (_quota_result(requirement) if requirement else
                         (False, "connected_db_estimate_unavailable"))
        if (requirement and not quota and reason in (
                "quota_program_unavailable", "quota_program_failed",
                "quota_volume_not_reported", "quota_format_unrecognized")):
            quota, reason = _cpanel_uapi_quota_result(requirement)
        out["quota_probe_available"] = quota is True
        out["quota_outcome"] = reason
        out.update(capacity_flags(free_bytes=free, db_bytes=db_bytes, quota_accepted=quota))
    except Exception as exc:
        # No exception text, DB names, table names, quotas, buyer details, paths.
        out["probe_error_type"] = type(exc).__name__
        out.update(capacity_flags(free_bytes=None, db_bytes=None, quota_accepted=False))
    print("MOJPROP_FULL_RESTORE_CAPACITY_READONLY=" + json.dumps(out, sort_keys=True))
    # Read-only diagnostic can safely report hold without returning an error.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
