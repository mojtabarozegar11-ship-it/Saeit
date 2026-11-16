#!/usr/bin/env python3
"""Real owner-only cPanel quota gap and fixed-scope disk inventory; NO writes.

Only metadata from connected Django information_schema, UAPI Quota and 'du -sk'
on eight allowlisted roots. Never prints exact volume, a path, database name,
file contents, user secrets or customer details. No cleanup is performed.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
OWNER = "zomorod2"
HEADROOM = 256 * 1024 * 1024
UAPI = "/usr/bin/uapi"
DU = "/usr/bin/du"
ENV = {"LC_ALL": "C", "PATH": "/usr/bin:/bin:/usr/local/bin",
       "HOME": str(HOME), "USER": OWNER, "LOGNAME": OWNER}
CANDIDATES = (
    ("code_staging", HOME / "Saeit-staging"),
    ("public_site", HOME / "mojplaywin.com"),
    ("python_virtualenv", HOME / "virtualenv"),
    ("catalog_backup_archive", HOME / ".mojplaywin-backups"),
    ("backend_backup_archive", HOME / ".mojplaywin-moj-prop-backups"),
    ("starter30_backup_archive", HOME / ".mojprop-starter30-backups"),
    ("private_cache", HOME / ".cache"),
    ("account_tmp", HOME / "tmp"),
)


def bucket_bytes(value):
    """Return only closed numeric ranges (MiB), never exact amounts."""
    if type(value) is not int or value < 0:
        return "unknown"
    mib = (value + 1024 * 1024 - 1) // (1024 * 1024)
    if mib == 0:
        return "0"
    for bound in (64, 256, 512, 1024, 2048, 4096, 8192):
        if mib <= bound:
            lower = 1 if bound == 64 else (64 if bound == 256 else
                    256 if bound == 512 else 512 if bound == 1024 else
                    1024 if bound == 2048 else 2048 if bound == 4096 else 4096)
            return f"{lower + (0 if lower == 1 else 1)}-{bound}"
    return ">8192"


def _safe_root(path):
    try:
        info = path.lstat()
        return (stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
                and info.st_uid == os.geteuid()
                and info.st_mode & stat.S_IWOTH == 0)
    except OSError:
        return False


def category_usage(path, *, runner=subprocess.run):
    if not _safe_root(path):
        return "unavailable", "unknown"
    try:
        r = runner([DU, "-sk", "--", str(path)], timeout=25,
                   check=True, capture_output=True, text=True, env=dict(ENV))
        if len(r.stdout) > 1024:
            return "unavailable", "unknown"
        match = re.fullmatch(r"([0-9]{1,18})\s+[^\n]+\n?", r.stdout)
        if match is None:
            return "unavailable", "unknown"
        # GNU du -k reports kibibytes; refuse absurd values.
        kib = int(match.group(1))
        if kib > (2**63 - 1) // 1024:
            return "unavailable", "unknown"
        return "counted", bucket_bytes(kib * 1024)
    except subprocess.TimeoutExpired:
        return "timeout", "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unavailable", "unknown"


def _db_estimate():
    from django.db import connection
    if connection.vendor != "mysql":
        raise ValueError("wrong DB driver")
    connection.ensure_connection()
    def select_only(execute, sql, params, many, context):
        if type(sql) is not str or not sql.lstrip().upper().startswith("SELECT "):
            raise PermissionError("read-only DB check")
        return execute(sql, params, many, context)
    with connection.execute_wrapper(select_only):
        with connection.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(DATA_LENGTH + INDEX_LENGTH), 0) "
                        "FROM information_schema.TABLES "
                        "WHERE TABLE_SCHEMA = DATABASE()")
            value = int(cur.fetchone()[0])
    if not 0 < value <= 100 * 1024**4:
        raise ValueError("unknown DB estimate")
    return value


def _quota_bytes():
    r = subprocess.run(
        [UAPI, "--output=json", "Quota", "get_quota_info"],
        timeout=15, check=True, capture_output=True, text=True, env=dict(ENV),
    )
    if len(r.stdout) > 16384:
        raise ValueError("oversize UAPI")
    doc = json.loads(r.stdout)
    if (type(doc) is not dict or type(doc.get("result")) is not dict
            or doc["result"].get("status") != 1
            or type(doc["result"].get("data")) is not dict):
        raise ValueError("invalid UAPI")
    data = doc["result"]["data"]
    # Only exact true representations; never accept Boolean, null or "01".
    for key in ("under_quota_overall", "under_megabyte_limit",
                "under_inode_limit"):
        flag = data.get(key)
        if not ((type(flag) is int and flag == 1)
                or (type(flag) is str and flag == "1")):
            raise ValueError("quota status not confirmed")
    def num(key):
        value = data[key]
        if type(value) not in (int, str):
            raise ValueError("quota numeric contract")
        item = Decimal(str(value))
        if not item.is_finite() or item < 0:
            raise ValueError("quota numeric range")
        return item
    if num("megabyte_limit") <= 0:
        raise ValueError("unverified unlimited quota")
    return int(num("megabytes_remain") * Decimal(1_000_000))


def main():
    try:
        owner = pwd.getpwuid(os.geteuid()).pw_name == OWNER
    except (KeyError, OSError):
        owner = False
    result = {
        "schema": "mojprop.cpanel.quota_gap_inventory.readonly.v1",
        "read_only": True, "owner_identity_verified": owner,
        "app_root_owner_verified": False,
        "db_estimate_bucket_mib": "unknown",
        "quota_free_bucket_mib": "unknown",
        "required_two_db_plus_headroom_bucket_mib": "unknown",
        "quota_shortfall_bucket_mib": "unknown",
        "combined_quota_capacity_sufficient": False,
        "category_usage": {},
        "database_dump_created": False,
        "isolated_restore_executed": False,
        "customer_records_accessed": False,
        "files_deleted_or_modified": False,
        "production_deploy_authorized": False,
        "payment_collected": False,
    }
    if not owner or not _safe_root(HOME) or not _safe_root(APP):
        print("MOJPROP_C113_QUOTA_GAP=" + json.dumps(result, sort_keys=True))
        return
    result["app_root_owner_verified"] = True
    try:
        os.chdir(APP)
        sys.path.insert(0, str(APP))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        import django
        django.setup()
        db = _db_estimate()
        needed = 2 * db + HEADROOM
        free = _quota_bytes()
        result["db_estimate_bucket_mib"] = bucket_bytes(db)
        result["quota_free_bucket_mib"] = bucket_bytes(free)
        result["required_two_db_plus_headroom_bucket_mib"] = bucket_bytes(needed)
        result["quota_shortfall_bucket_mib"] = bucket_bytes(max(0, needed - free))
        result["combined_quota_capacity_sufficient"] = free >= needed
    except Exception as err:
        # Only the exception CLASS, never its text: it can include SQL/paths.
        result["probe_error_class"] = type(err).__name__
    for label, path in CANDIDATES:
        state, size = category_usage(path)
        result["category_usage"][label] = {"state": state, "mib_bucket": size}
    print("MOJPROP_C113_QUOTA_GAP=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
