"""Store-only backup prerequisite: metadata and quota, never customer rows.
Run as the existing cPanel account with the existing Python interpreter and -B.
No dump, migration, mail, restart, or backup creation; no identifiers in output.
"""
import json
import math
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys

ROOT = Path("/home/zomorod2/Saeit-staging")
DEST = Path("/home/zomorod2/separated-backups/20261119")
UAPI_PATHS = (Path("/usr/bin/uapi"), Path("/usr/local/cpanel/bin/uapi"))
OWNER = "zomorod2"
SEEDS = ("core.PaymentIntent", "core.PaymentWebhookEvent", "core.LedgerEntry",
         "core.Order", "core.OrderItem", "core.Product", "core.GuestOrderEmail",
         "core.GuestRecoveryToken", "core.GuestRecoveryRate")
MAX_ROWS = 20000

def bounded(cursor, sql):
    cursor.execute(sql)
    rows = cursor.fetchmany(MAX_ROWS + 1)
    if len(rows) > MAX_ROWS:
        raise ValueError("metadata limit")
    return rows

def boundary(seeds, tables, edges):
    """Edges point from dependent to required parent; closure is not row scope."""
    known = set(tables)
    selected = set(seeds) & known
    edges = set(edges)
    while True:
        expanded = selected | {p for c, p in edges if c in selected and p in known}
        if expanded == selected:
            break
        selected = expanded
    return {
        "seed_tables_present": len(set(seeds) & known),
        "seed_tables_missing": len(set(seeds) - known),
        "required_table_count": len(selected),
        "additional_required_tables": len(selected - set(seeds)),
        "incoming_boundary_edges": sum(c not in selected and p in selected for c, p in edges),
        "missing_parent_edges": sum(c in selected and p not in known for c, p in edges),
        "estimated_required_table_bytes": sum(tables[t][1] for t in selected),
        "required_tables_transactional": bool(selected) and all(tables[t][0] == "InnoDB" for t in selected),
        "row_scope_proven": False,
    }

def quota_fields(document):
    if (document.get("module") != "Quota" or
        document.get("func") != "get_local_quota_info"):
        raise ValueError("unexpected quota response")
    result = document["result"]
    if type(result.get("status")) is not int or result["status"] != 1 or result.get("errors") or result.get("warnings"):
        raise ValueError("quota unavailable")
    data = result["data"]
    keys = ("bytes_used", "byte_limit", "inodes_used", "inode_limit")
    if any(type(data.get(k)) is not int or data[k] < 0 for k in keys):
        raise ValueError("invalid quota counters")
    return {**{k: data[k] for k in keys},
            "local_byte_headroom": max(0, data["byte_limit"]-data["bytes_used"]) if data["byte_limit"] else None,
            "local_inode_headroom": max(0, data["inode_limit"]-data["inodes_used"]) if data["inode_limit"] else None,
            "account_total_quota_proven": False}

def account_quota_fields(document):
    """Validate account-wide quota separately; never infer it from statvfs."""
    if document.get("module") != "Quota" or document.get("func") != "get_quota_info":
        raise ValueError("unexpected account quota response")
    result = document["result"]
    if type(result.get("status")) is not int or result["status"] != 1 or result.get("errors") or result.get("warnings"):
        raise ValueError("account quota unavailable or ambiguous")
    data = result["data"]
    disk = ("megabyte_limit", "megabytes_used", "megabytes_remain")
    inode = ("inode_limit", "inodes_used", "inodes_remain")
    flags = ("under_megabyte_limit", "under_inode_limit", "under_quota_overall")
    if any(type(data.get(k)) not in (int,float) or not math.isfinite(data[k]) or data[k] < 0 for k in disk):
        raise ValueError("invalid account disk counters")
    if any(type(data.get(k)) is not int or data[k] < 0 for k in inode):
        raise ValueError("invalid account inode counters")
    if any(type(data.get(k)) is not int or data[k] not in (0,1) for k in flags):
        raise ValueError("invalid account quota status")
    # Zero means unlimited/disabled, not known usable capacity.
    disk_remaining = min(data["megabytes_remain"], max(0, data["megabyte_limit"] - data["megabytes_used"])) if data["megabyte_limit"] else None
    inode_remaining = min(data["inodes_remain"], max(0, data["inode_limit"] - data["inodes_used"])) if data["inode_limit"] else None
    return {**{k: data[k] for k in disk + inode + flags},
            "account_disk_headroom_reported_mb": disk_remaining,
            "account_inode_headroom_reported": inode_remaining,
            "account_total_quota_observed": True,
            "backup_capacity_proven": False}

def quota(function="get_local_quota_info"):
    if function not in ("get_local_quota_info", "get_quota_info"):
        raise ValueError("unsupported read-only quota function")
    parser = quota_fields if function == "get_local_quota_info" else account_quota_fields
    attempts = []
    for binary in UAPI_PATHS:
        try:
            st = binary.stat()
            if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
                raise ValueError("unsafe UAPI executable")
        except (OSError, ValueError) as exc:
            attempts.append(type(exc).__name__)
            continue
        for user_arg in (["--user=" + OWNER], []):
            try:
                p = subprocess.run([str(binary), "--output=json", *user_arg, "Quota", function],
                                   capture_output=True, timeout=8, check=False)
                if p.returncode != 0:
                    attempts.append("nonzero_exit_" + str(p.returncode))
                    continue
                if len(p.stdout) > 65536:
                    raise ValueError("quota response too large")
                data = parser(json.loads(p.stdout))
                return {"success": True, "data": data, "prior_attempts": attempts}
            except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
                attempts.append(type(exc).__name__)
    return {"success": False, "attempts": attempts}


def inspect():
    out = {"schema": "mpw.store_backup_boundary.readonly.v3", "read_only": True,
           "customer_rows_read": False, "dump_executed": False,
           "restore_verified": False, "release_authorized": False}
    if pwd.getpwuid(os.getuid()).pw_name != OWNER or ROOT.resolve() != ROOT:
        return {**out, "owner_runtime_verified": False}
    out["owner_runtime_verified"] = True
    try:
        out["local_quota"] = quota()
    except Exception as exc:
        out["quota_error_type"] = type(exc).__name__
    try:
        out["account_quota"] = quota("get_quota_info")
    except Exception as exc:
        out["account_quota_error_type"] = type(exc).__name__
    try:
        if DEST.resolve() == DEST and DEST.is_dir():
            st = DEST.stat()
            if st.st_uid == os.getuid() and not st.st_mode & 0o077:
                out["destination_private"] = True
                v = os.statvfs(DEST)
                out["filesystem_available_bytes"] = v.f_bavail * v.f_frsize
        sys.dont_write_bytecode = True
        os.chdir(ROOT)
        sys.path.insert(0, str(ROOT))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        django.setup()
        from django.apps import apps
        from django.db import connection
        from django.contrib.auth import get_user_model
        if connection.vendor != "mysql":
            return out
        seeds = {get_user_model()._meta.db_table}
        missing_labels = 0
        for label in SEEDS:
            try:
                seeds.add(apps.get_model(label)._meta.db_table)
            except LookupError:
                missing_labels += 1
        seeds.update(m._meta.db_table for m in apps.get_app_config("mpw_commerce").get_models())
        with connection.cursor() as cursor:
            tables = {n: (e, int(s)) for n,e,s in bounded(cursor,
                "SELECT TABLE_NAME,ENGINE,COALESCE(DATA_LENGTH,0)+COALESCE(INDEX_LENGTH,0) "
                "FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'")}
            raw = bounded(cursor,
                "SELECT TABLE_NAME,REFERENCED_TABLE_NAME,REFERENCED_TABLE_SCHEMA=DATABASE() "
                "FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() "
                "AND REFERENCED_TABLE_NAME IS NOT NULL")
        edges = {(c,p if same else None) for c,p,same in raw}
        # Include ORM relationships without database constraints, including through tables.
        for m in apps.get_models(include_auto_created=True):
            for f in m._meta.local_fields:
                target = getattr(getattr(f, "remote_field", None), "model", None)
                if hasattr(target, "_meta"):
                    edges.add((m._meta.db_table, target._meta.db_table))
        out["metadata"] = boundary(seeds,tables,edges)
        out["metadata"]["missing_seed_models"] = missing_labels
        out["metadata"]["cross_schema_foreign_keys"] = sum(not same for _,_,same in raw)
        out["metadata"]["total_base_tables"] = len(tables)
    except Exception as exc:
        out["metadata_error_type"] = type(exc).__name__
    return out

if __name__ == "__main__":
    print("MPW_STORE_BACKUP_BOUNDARY_READONLY="+json.dumps(inspect(),sort_keys=True))
