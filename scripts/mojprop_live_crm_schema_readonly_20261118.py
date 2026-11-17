#!/usr/bin/env python3
"""Owner-only cPanel SELECT-only CRM schema verification (zero buyer rows).

Confirms exact columns and UNIQUE request_id required by already-written
MOJ-PROP-01 interest intake. This is NOT deployment, full DB restore proof,
a transaction, or authorization to receive 30 TRX.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import sys

ROOT = Path("/home/zomorod2/Saeit-staging")
APP_USER = "zomorod2"
TABLE = "core_mojproprequest"
REQUIRED = frozenset((
    "request_id", "name", "email", "route", "horizon", "notes",
    "product_id", "consent", "status", "source", "ip_hash",
    "user_agent", "created_at",
))


def evaluate(columns, indexes):
    """Use ONLY metadata; identify exact single-column unique request key."""
    if type(columns) not in (tuple, list, set, frozenset):
        raise ValueError("Missing column metadata")
    columns_set = set(columns)
    if any(type(x) is not str or len(x) > 100 for x in columns_set):
        raise ValueError("Malformed column metadata")
    if type(indexes) not in (tuple, list):
        raise ValueError("Missing index metadata")
    groups = {}
    for entry in indexes:
        if not isinstance(entry, (tuple, list)) or len(entry) != 4:
            raise ValueError("Invalid index metadata")
        key, nonunique, column, position = entry
        if type(key) is not str or type(column) is not str:
            raise ValueError("Unsafe index metadata")
        if type(nonunique) is not int or type(position) is not int:
            raise ValueError("Invalid index types")
        groups.setdefault(key, []).append((nonunique, column, position))
    unique_id = any(
        len(parts) == 1 and parts[0] == (0, "request_id", 1)
        for parts in groups.values()
    )
    complete = REQUIRED <= columns_set
    return {
        "table_exists": bool(columns_set),
        "required_columns_count": len(REQUIRED),
        "required_columns_present": complete,
        "single_column_unique_request_id_present": unique_id,
        "schema_allows_existing_intake_without_new_migration":
            complete and unique_id,
        "customer_rows_queried": False,
        "data_written": False,
    }


def inspect(connection):
    if connection.vendor != "mysql":
        raise ValueError("Unexpected database type")
    # Establish the session BEFORE the SELECT-only query guard. MySQL
    # driver/session initialization may use SET but not business writes.
    connection.ensure_connection()

    def allow_select(execute, sql, params, many, context):
        verb = str(sql).lstrip().upper().split(None, 1)
        if not verb or verb[0] != "SELECT":
            raise PermissionError("Non-SELECT database statement refused")
        return execute(sql, params, many, context)

    with connection.execute_wrapper(allow_select):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
                [TABLE],
            )
            column_rows = cursor.fetchall()
            cursor.execute(
                "SELECT INDEX_NAME, NON_UNIQUE, COLUMN_NAME, SEQ_IN_INDEX "
                "FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
                [TABLE],
            )
            index_rows = cursor.fetchall()
    return evaluate([x[0] for x in column_rows], index_rows)


def main():
    result = {
        "schema": "mojprop.crm.live_schema.readonly.v1",
        "read_only": True,
        "owner_identity_verified": False,
        "metadata_query_completed": False,
        "table_exists": None,
        "required_columns_count": len(REQUIRED),
        "required_columns_present": None,
        "single_column_unique_request_id_present": None,
        "schema_allows_existing_intake_without_new_migration": None,
        "customer_rows_queried": False,
        "data_written": False,
        "production_deploy_authorized": False,
        "offsite_full_restore_proven": False,
        "payment_or_enrollment_created": False,
    }
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != APP_USER:
            raise PermissionError("Not the authorized cPanel application user")
        if ROOT.is_symlink() or not ROOT.is_dir():
            raise ValueError("Unavailable existing owner staging root")
        result["owner_identity_verified"] = True
        os.chdir(ROOT)
        sys.path.insert(0, str(ROOT))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        import django
        django.setup()
        from django.db import connection
        result.update(inspect(connection))
        result["metadata_query_completed"] = True
    except Exception as exc:
        result["probe_error_type"] = type(exc).__name__
    print("MOJPROP_LIVE_CRM_SCHEMA_READONLY=" +
          json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
