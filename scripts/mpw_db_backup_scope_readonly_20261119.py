"""Classify local backup scope and capacity without reading data rows or dumping SQL."""
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path("/home/zomorod2/Saeit-staging")
DEST = Path("/home/zomorod2/separated-backups/20261119")
STORE_MODELS = (
    "core.PaymentIntent", "core.PaymentWebhookEvent", "core.LedgerEntry",
    "core.Order", "core.OrderItem", "core.Product",
    "core.GuestOrderEmail", "core.GuestRecoveryToken", "core.GuestRecoveryRate",
)



# These known Django names are only used locally; neither table names nor
# database/customer identifiers are printed.
PROP_TABLES = frozenset("prop_firm_" + name for name in (
    "propplan1invoice", "propplan1receipt", "tronsettlementledger",
    "proprewardreserveallocation", "proprewardcommitment",
    "propsimulationaccount", "propsimulationidentity",
    "propsimulationloginchallenge", "propsimulationinvoiceowner",
    "propsimulationevent",
))

def dependency_scope(rows, edges, store, user_table):
    sizes = {name: int(size) for name, _, size in rows}
    prop = PROP_TABLES & sizes.keys()
    closure = set(prop)
    # Follow references from child to its required parent. Never include
    # every unrelated child of the shared auth or migration tables.
    for _ in range(len(sizes) + 1):
        added = {parent for child, parent, same_schema in edges
                 if child in closure and same_schema and parent in sizes}
        if added <= closure:
            break
        closure.update(added)
    outgoing = [(child, parent) for child, parent, same_schema in edges
                if child in closure and (not same_schema or parent not in sizes)]
    incoming = {(child, parent) for child, parent, same_schema in edges
                if same_schema and child not in closure and parent in closure}
    return {
        "expected_prop_tables": len(PROP_TABLES),
        "present_prop_tables": len(prop),
        "missing_prop_tables": len(PROP_TABLES - prop),
        "prop_table_bytes_estimated": sum(sizes[t] for t in prop),
        "parent_closure_tables": len(closure),
        "parent_closure_bytes_estimated": sum(sizes[t] for t in closure),
        "shared_store_tables_in_closure": len(closure & store),
        "shared_auth_table_in_closure": user_table in closure,
        "external_or_missing_parent_edges": len(outgoing),
        "incoming_dependencies_from_other_tables": len(incoming),
        "foreign_key_edges_observed": len(edges),
        "backup_scope_approved": False,
        "independent_restore_proven": False,
    }


def kernel_quota_observation():
    """Report only explicit numeric hard limits; no inference from filesystem free."""
    import pwd
    import stat
    import subprocess
    result = {"quota_cli_available": False, "kernel_quota_recognized": False,
              "kernel_quota_entries": 0, "kernel_quota_all_finite": False}
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
            return result
        binary = shutil.which("quota", path="/usr/bin:/bin")
        if not binary:
            return result
        info = os.stat(binary)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022 or info.st_uid != 0:
            return result
        result["quota_cli_available"] = True
        proc = subprocess.run([binary, "-w", "-v", "-p"], capture_output=True,
                              timeout=8, env={"LC_ALL":"C", "PATH":"/usr/bin:/bin"})
        if len(proc.stdout) > 16000 or proc.returncode not in (0, 1):
            return result
        lines = proc.stdout.decode("ascii", "strict").splitlines()
        # Linux quota normal block output uses KiB; -p keeps grace as epoch.
        # Reject unfamiliar formats, overflow markers, and unrecognized rows.
        data = [line.split() for line in lines if line.strip()
                and not line.lstrip().startswith(("Disk quotas", "Filesystem"))]
        if not data or any(len(row) != 9 or
                           not all(v.isdigit() for v in row[1:]) for row in data):
            return result
        limits = [(int(row[1]), int(row[2]), int(row[3])) for row in data]
        result["kernel_quota_recognized"] = True
        result["kernel_quota_entries"] = len(limits)
        if all(hard > 0 for _, _, hard in limits):
            result["kernel_quota_all_finite"] = True
            result["minimum_observed_hard_headroom_bytes"] = min(max(0, hard-used)*1024 for used, _, hard in limits)
            result["any_observed_soft_limit_exceeded"] = any(soft > 0 and used >= soft for used, soft, _ in limits)
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        pass
    return result


def inspect():
    report = {"read_only": True, "db_rows_read": False, "dump_executed": False,
              "external_transfer": False, "release_authorized": False,
              "schema_metadata_available": False, "local_dump_client_available": False}
    if not ROOT.is_dir() or ROOT.resolve() != ROOT:
        return report
    try:
        os.chdir(ROOT)
        sys.path.insert(0, str(ROOT))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        django.setup()
        from django.conf import settings
        from django.db import connection
        from django.apps import apps
        from django.contrib.auth import get_user_model
        if connection.vendor != "mysql":
            return report
        store = {get_user_model()._meta.db_table}
        for label in STORE_MODELS:
            try:
                store.add(apps.get_model(label)._meta.db_table)
            except LookupError:
                pass
        store.update(m._meta.db_table for m in apps.get_app_config("mpw_commerce").get_models())
        # Names are used locally for classification only, never emitted.
        with connection.cursor() as cursor:
            cursor.execute("""SELECT TABLE_NAME, ENGINE, COALESCE(DATA_LENGTH,0)+COALESCE(INDEX_LENGTH,0)
            FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'""")
            rows = cursor.fetchmany(5001)
        if len(rows)>5000:
            return report
        report["schema_metadata_available"] = True
        with connection.cursor() as cursor:
            cursor.execute("""SELECT TABLE_NAME, REFERENCED_TABLE_NAME,
                REFERENCED_TABLE_SCHEMA=DATABASE()
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL""")
            fk_rows = cursor.fetchmany(20001)
        report["prop_foreign_key_metadata_complete"] = len(fk_rows) <= 20000
        if report["prop_foreign_key_metadata_complete"]:
            report["prop_dependency_scope"] = dependency_scope(rows, set(fk_rows), store, get_user_model()._meta.db_table)
        report["kernel_quota"] = kernel_quota_observation()
        report["table_count"] = len(rows)
        report["store_related_table_count"] = sum(name in store for name, _, _ in rows)
        report["other_table_count"] = sum(name not in store for name, _, _ in rows)
        report["estimated_database_bytes"] = sum(int(size) for _, _, size in rows)
        report["estimated_store_related_table_bytes"] = sum(int(size) for name, _, size in rows if name in store)
        report["all_base_tables_transactional"] = bool(rows) and all(engine=="InnoDB" for _, engine, _ in rows)
        report["local_dump_client_available"] = bool(shutil.which("mariadb-dump") or shutil.which("mysqldump"))
        report["backup_directory_private"] = DEST.is_dir() and DEST.resolve()==DEST and not DEST.stat().st_mode & 0o077
        report["filesystem_free_bytes"] = shutil.disk_usage(DEST).free if report["backup_directory_private"] else 0
        report["dedicated_store_database_proven"] = False
        report["shared_table_scope_requires_review"] = True
        report["account_quota_headroom_proven"] = False
    except Exception as exc:
        report["error_type"] = type(exc).__name__
    return report


if __name__ == "__main__":
    print("MPW_DB_BACKUP_SCOPE_READONLY="+json.dumps(inspect(), sort_keys=True))
