#!/usr/bin/env python3
"""C168: classify real staging MySQL storage engines, without table names/rows.

ONE bounded information_schema query, no dump, DDL, user table SELECT,
customer records, MySQL credential/path printing, backup/restore or deploy.
An all-InnoDB result is only a *candidate* for --single-transaction: it does
not prove a consistent backup because concurrent DDL and the running Passenger
DB identity, routines, events, triggers and media remain unproven.
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
MAX_ENGINE_TYPES = 16
MAX_TABLES = 200000
SQL = (
    "SELECT ENGINE, COUNT(*) FROM information_schema.TABLES "
    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE' "
    "GROUP BY ENGINE"
)
PREFIX = "MOJPROP_C168_MYSQL_ENGINE_INVENTORY_READONLY="


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


def classify_engines(rows) -> dict | None:
    """Fail closed for malformed, duplicate or out-of-range engine aggregates."""
    if not isinstance(rows, (tuple, list)) or not 1 <= len(rows) <= MAX_ENGINE_TYPES:
        return None
    seen = set()
    result = {"innodb_tables": 0, "other_engine_tables": 0,
              "unknown_engine_tables": 0, "visible_base_tables": 0,
              "engine_types": 0, "engines_all_innodb": False,
              "single_transaction_candidate_only": False,
              "production_identity_proven": False,
              "consistent_snapshot_proven": False}
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != 2:
            return None
        engine, count = row
        if engine is not None and (type(engine) is not str or not engine or len(engine) > 48):
            return None
        if type(count) is not int or not 1 <= count <= MAX_TABLES:
            return None
        k = engine.upper() if engine is not None else "<NULL>"
        if k in seen:
            return None
        seen.add(k)
        if result["visible_base_tables"] + count > MAX_TABLES:
            return None
        result["visible_base_tables"] += count
        result["engine_types"] += 1
        if k == "INNODB":
            result["innodb_tables"] += count
        elif k == "<NULL>":
            result["unknown_engine_tables"] += count
        else:
            result["other_engine_tables"] += count
    result["engines_all_innodb"] = result["visible_base_tables"] > 0 and result["innodb_tables"] == result["visible_base_tables"]
    result["single_transaction_candidate_only"] = result["engines_all_innodb"]
    return result


def read_engines(db_connection) -> dict | None:
    with db_connection.cursor() as cursor:
        cursor.execute(SQL)
        rows = cursor.fetchmany(MAX_ENGINE_TYPES + 1)
        return classify_engines(rows)


def report() -> dict:
    result = {
        "schema": "mojprop.cpanel.mysql_engine_inventory.readonly.c168.v1",
        "read_only": True, "owner_identity_verified": False,
        "staging_source_safe": False, "configured_backend_mysql": False,
        "database_query_attempted": False, "status": "not_attempted",
        "engine_aggregate": None,
        "table_names_or_rows_read": False,
        "db_name_or_credentials_exposed": False,
        "routines_triggers_events_inventoried": False,
        "production_passenger_db_identity_proven": False,
        "database_backup_created": False,
        "independent_full_restore_verified": False,
        "production_release_authorized": False,
        "payment_created": False, "cost_incurred": False,
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
        db = settings.DATABASES.get("default")
        if type(db) is not dict or db.get("ENGINE") != "django.db.backends.mysql" or not db.get("NAME"):
            result["status"] = "unconfigured_or_non_mysql"
            return result
        result["configured_backend_mysql"] = True
        from django.db import connections
        conn = connections["default"]
        if conn.vendor != "mysql":
            result["status"] = "backend_identity_mismatch"
            return result
        result["database_query_attempted"] = True
        try:
            agg = read_engines(conn)
            if agg is None:
                result["status"] = "malformed_or_unavailable_engine_aggregate"
            else:
                result["engine_aggregate"] = agg
                result["status"] = "engine_aggregate_read_success"
        except Exception:
            result["status"] = "database_query_unavailable"
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception:
        result["status"] = "config_or_dependency_unavailable"
    return result


if __name__ == "__main__":
    print(PREFIX + json.dumps(report(), sort_keys=True, separators=(",", ":")))
