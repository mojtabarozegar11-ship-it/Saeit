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
