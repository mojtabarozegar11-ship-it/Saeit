#!/usr/bin/env python3
"""C162: one bounded read-only MySQL metadata query on verified staging DB.

No customer-table SELECT, backup/dump, transaction write, migration, server
change, payment, secret/path/name logging or external network. The only SQL
is a fixed SELECT of aggregate table counts/approximate DATA_LENGTH and
INDEX_LENGTH from information_schema.TABLES for the already selected default
database (DATABASE()). Approximate metadata != dump size, consistent snapshot,
backup correctness, offhost copy, or a tested isolated restore.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import stat
import sys

OWNER = "zomorod2"
HOME = Path("/home/zomorod2")
ROOT = HOME / "Saeit-staging"
MAX_ESTIMATED_BYTES = 1000 * 1024**4

SQL = (
    "SELECT COUNT(*), COALESCE(SUM(COALESCE(DATA_LENGTH,0)),0), "
    "COALESCE(SUM(COALESCE(INDEX_LENGTH,0)),0) "
    "FROM information_schema.TABLES "
    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'"
)


def safe_staging(uid: int) -> bool:
    for path, directory in ((HOME, True), (ROOT, True),
                            (ROOT / "config", True),
                            (ROOT / "config/settings.py", False)):
        try:
            item = path.lstat()
        except OSError:
            return False
        if item.st_uid != uid or item.st_mode & 0o022:
            return False
        if directory:
            if not stat.S_ISDIR(item.st_mode):
                return False
        elif not stat.S_ISREG(item.st_mode) or item.st_nlink != 1:
            return False
    return True


def classify_aggregate(row) -> dict | None:
    """Accept only bounded whole-number aggregate data; no user rows/names."""
    if type(row) not in (tuple, list) or len(row) != 3:
        return None
    counts = []
    for n in row:
        if type(n) is int:
            value = n
        elif type(n) is float and n.is_integer():
            value = int(n)
        else:
            # Decimal is accepted only via exact integral conversion.
            from decimal import Decimal
            if type(n) is not Decimal or not n.is_finite() or n != n.to_integral_value():
                return None
            value = int(n)
        if value < 0 or value > MAX_ESTIMATED_BYTES:
            return None
        counts.append(value)
    table_count, data_bytes, index_bytes = counts
    if table_count > 200000 or data_bytes + index_bytes > MAX_ESTIMATED_BYTES:
        return None
    return {
        "visible_base_tables": table_count,
        "approx_data_bytes": data_bytes,
        "approx_index_bytes": index_bytes,
        "approx_total_bytes": data_bytes + index_bytes,
        "metadata_only": True,
        "dump_size_predicted_exactly": False,
    }


def read_one_mysql_aggregate(db_connection) -> dict | None:
    """One fixed read-only SQL; no parameters or table/customer identifiers."""
    with db_connection.cursor() as cursor:
        cursor.execute(SQL)
        return classify_aggregate(cursor.fetchone())


def report() -> dict:
    result = {
        "schema": "mojprop.owner.mysql_information_schema.readonly.c162.v1",
        "read_only": True, "owner_identity_verified": False,
        "staging_source_safe": False,
        "effective_config_loaded": False,
        "configured_backend_mysql": False,
        "connection_attempted": False,
        "metadata_status": "not_attempted",
        "aggregate": None,
        "database_name_or_password_emitted": False,
        "customer_table_data_read": False,
        "read_only_sql_metadata_only": True,
        "mysql_dump_or_archive_created": False,
        "mysql_consistent_snapshot_proven": False,
        "offhost_encrypted_database_backup_verified": False,
        "independent_full_db_app_media_restore_proven": False,
        "actual_live_passenger_db_identity_proven": False,
        "production_release_authorized": False,
        "payment_created": False,
        "cost_incurred": False,
    }
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != OWNER:
            return result
        result["owner_identity_verified"] = True
        if not safe_staging(os.geteuid()):
            return result
        result["staging_source_safe"] = True
        os.chdir(ROOT)
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        from django.conf import settings
        cfg = settings.DATABASES.get("default")
        result["effective_config_loaded"] = True
        if type(cfg) is not dict or cfg.get("ENGINE") != "django.db.backends.mysql" or not cfg.get("NAME"):
            result["metadata_status"] = "wrong_or_unconfigured_backend"
            return result
        result["configured_backend_mysql"] = True
        # django.db.connections creates only a local wrapper until cursor use.
        # The subsequent single SELECT never accesses application table rows.
        from django.db import connections
        conn = connections["default"]
        if conn.vendor != "mysql":
            result["metadata_status"] = "backend_mismatch"
            return result
        result["connection_attempted"] = True
        try:
            agg = read_one_mysql_aggregate(conn)
            if agg is None:
                result["metadata_status"] = "invalid_or_unavailable_aggregate"
            else:
                result["aggregate"] = agg
                result["metadata_status"] = "aggregate_read_success"
        except Exception:
            # Exceptions may contain credentials, database names or internal
            # paths. Never print, forward or serialize the exception.
            result["metadata_status"] = "connection_or_metadata_unavailable"
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception:
        result["metadata_status"] = "settings_or_dependency_unavailable"
    return result


if __name__ == "__main__":
    print("MOJPROP_C162_MYSQL_METADATA_SIZE_READONLY=" +
          json.dumps(report(), sort_keys=True, separators=(",", ":")))
