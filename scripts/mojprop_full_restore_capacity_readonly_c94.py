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
