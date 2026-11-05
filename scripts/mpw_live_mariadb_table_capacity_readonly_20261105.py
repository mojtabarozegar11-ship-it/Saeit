#!/usr/bin/env python3
"""Read-only table-size inventory for MojPlayWin's effective MariaDB schema.

Only information_schema metadata is examined; no rows or customer fields are
selected, and the database name and connection credentials are never logged.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path("/home/zomorod2/Saeit-staging")
if not ROOT.is_dir() or ROOT.is_symlink():
    raise RuntimeError("UNEXPECTED_LIVE_RUNTIME_ROOT")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()
from django.db import connection

TARGET_TABLES = {
    "core_order", "core_orderitem", "core_paymentintent",
    "core_paymentwebhookevent", "core_ledgerentry", "core_guestorderemail",
    "core_guestrecoverytoken", "core_guestrecoveryrate",
    "mpw_commerce_commercefulfillment", "django_migrations",
}


def group(name):
    if name.startswith("mpw_commerce_"):
        return "mpw_commerce"
    if name.startswith("core_"):
        return "core"
    if name.startswith(("django_", "auth_", "account_", "sessions_")):
        return "django_auth"
    return "other"


def run():
    if connection.vendor != "mysql":
        raise RuntimeError("EXPECTED_MARIADB_BACKEND")
    with connection.cursor() as cur:
        cur.execute("""
            SELECT TABLE_NAME, COALESCE(DATA_LENGTH, 0),
                   COALESCE(INDEX_LENGTH, 0), COALESCE(TABLE_ROWS, 0)
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'
        """)
        rows = cur.fetchall()
    if not rows or len(rows) > 5000:
        raise RuntimeError("DATABASE_TABLE_COUNT_UNEXPECTED")
    totals = {name: {"tables": 0, "data_bytes": 0, "index_bytes": 0}
              for name in ("mpw_commerce", "core", "django_auth", "other")}
    clean = []
    for table, data_size, index_size, estimated_rows in rows:
        name = str(table)
        if not re.fullmatch(r"[A-Za-z0-9_]{1,100}", name):
            raise RuntimeError("UNEXPECTED_TABLE_NAME")
        d = max(0, int(data_size))
        i = max(0, int(index_size))
        count = max(0, int(estimated_rows))
        totals[group(name)]["tables"] += 1
        totals[group(name)]["data_bytes"] += d
        totals[group(name)]["index_bytes"] += i
        clean.append({"table": name, "allocated_bytes": d + i,
                      "estimated_rows": count})
    clean.sort(key=lambda row: row["allocated_bytes"], reverse=True)
    targeted = [r for r in clean if r["table"] in TARGET_TABLES]
    report = {
        "source": "live_information_schema_tables",
        "engine": "mysql",
        "table_count": len(clean),
        "total_allocated_bytes": sum(r["allocated_bytes"] for r in clean),
        "by_group": totals,
        "largest_tables": clean[:12],
        "purchase_and_recovery_tables": targeted,
        "inno_db_size_is_estimate_not_dump_size": True,
        "customer_rows_or_values_read": False,
        "database_name_logged": False,
        "production_writes": False,
        "payments_or_emails": False,
    }
    print("MPW_MARIADB_CAPACITY_READONLY=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    run()
