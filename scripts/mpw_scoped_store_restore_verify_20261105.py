#!/usr/bin/env python3
"""Verify real scoped store MariaDB restoration in an isolated Docker container.

Run only after importing the cPanel-produced SQL dump into `mpw_isolated`.
Reads container-local table metadata and aggregate counts, never customer rows.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

TABLES = frozenset({
    "auth_user", "core_factoryrun", "core_guestorderemail",
    "core_guestrecoveryrate", "core_guestrecoverytoken",
    "core_knowledgearticle", "core_ledgerentry", "core_order",
    "core_orderitem", "core_paymentintent", "core_paymentwebhookevent",
    "core_product", "core_report", "core_researchproject",
    "mpw_commerce_commercefulfillment", "django_migrations",
})
IDENTIFIER = re.compile(r"[A-Za-z0-9_]{1,100}\Z")


def safe_identifier(value):
    if not IDENTIFIER.fullmatch(value):
        raise RuntimeError("UNSAFE_SQL_IDENTIFIER")
    return "`" + value + "`"


def orphan_query(edges):
    """Build SQL only from vetted information_schema FK identifiers."""
    if not edges:
        raise RuntimeError("EMPTY_FOREIGN_KEY")
    child = safe_identifier(edges[0][0])
    parent = safe_identifier(edges[0][2])
    join = []
    not_null = []
    for c_table, c_col, p_table, p_col in edges:
        if c_table != edges[0][0] or p_table != edges[0][2]:
            raise RuntimeError("INCONSISTENT_COMPOSITE_FK")
        c, p = safe_identifier(c_col), safe_identifier(p_col)
        join.append(f"c.{c}=p.{p}")
        not_null.append(f"c.{c} IS NOT NULL")
    return (f"SELECT COUNT(*) FROM {child} c LEFT JOIN {parent} p ON "
            + " AND ".join(join) + " WHERE "
            + " AND ".join(not_null)
            + f" AND p.{safe_identifier(edges[0][3])} IS NULL")


def query(label, sql):
    if not re.fullmatch(r"mpw-drill-[0-9]+-[0-9]+", label):
        raise RuntimeError("UNEXPECTED_DOCKER_LABEL")
    q = subprocess.run([
        "docker", "exec", label, "mariadb", "--no-defaults", "-uroot",
        "--batch", "--skip-column-names", "--database=mpw_isolated",
        "--execute=" + sql,
    ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=100)
    if q.returncode or len(q.stdout) > 50000:
        raise RuntimeError("ISOLATED_SQL_QUERY_FAILED")
    return q.stdout.decode("utf-8", "replace").strip()


def verify(label):
    names = set(query(label, """
        SELECT TABLE_NAME FROM information_schema.TABLES
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'
    """).splitlines())
    if names != TABLES:
        raise RuntimeError("ISOLATED_TABLE_SET_MISMATCH")
    rows = query(label, """
        SELECT TABLE_NAME,COLUMN_NAME,REFERENCED_TABLE_NAME,
               REFERENCED_COLUMN_NAME,CONSTRAINT_NAME,ORDINAL_POSITION
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY TABLE_NAME,CONSTRAINT_NAME,ORDINAL_POSITION
    """)
    constraints = {}
    for line in rows.splitlines():
        fields = line.split("\t")
        if len(fields) != 6:
            raise RuntimeError("ISOLATED_FK_METADATA_INVALID")
        child, c_col, parent, p_col, cname, ordinal = fields
        if parent not in TABLES or child not in TABLES:
            raise RuntimeError("ISOLATED_FOREIGN_TABLE_REFERENCE")
        for identifier in (child, c_col, parent, p_col, cname):
            safe_identifier(identifier)
        constraints.setdefault((child, cname), []).append((child, c_col, parent, p_col))
    if not constraints:
        raise RuntimeError("ISOLATED_FK_NOT_PRESENT")
    for edge_set in constraints.values():
        orphan_count = int(query(label, orphan_query(edge_set)))
        if orphan_count:
            raise RuntimeError("ISOLATED_ORPHANED_FOREIGN_KEYS")
    important = {}
    for table in ("core_order", "core_orderitem", "core_paymentintent",
                  "core_paymentwebhookevent", "core_ledgerentry",
                  "core_guestorderemail", "core_guestrecoverytoken",
                  "mpw_commerce_commercefulfillment"):
        important[table] = int(query(label, "SELECT COUNT(*) FROM " + safe_identifier(table)))
    if not important["core_order"] or not important["core_paymentintent"]:
        raise RuntimeError("ISOLATED_SALES_DATA_MISSING")
    migrations = int(query(label, """
        SELECT COUNT(*) FROM django_migrations
        WHERE app='core' AND name LIKE '0049%'
    """))
    if migrations != 1:
        raise RuntimeError("ISOLATED_RECOVERY_MIGRATION_NOT_PRESENT")
    report = {
        "classification": "ISOLATED_SCOPED_STORE_RESTORE",
        "table_count": len(names),
        "fk_constraints_checked": len(constraints),
        "foreign_key_orphan_count": 0,
        "restore_migration_0049_present": True,
        "order_count": important["core_order"],
        "payment_intent_count": important["core_paymentintent"],
        "fulfillment_count": important["mpw_commerce_commercefulfillment"],
        "full_database_restore": False,
        "customer_values_logged": False,
        "production_writes": False,
    }
    print("MPW_SCOPED_STORE_ISOLATED_RESTORE=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("ISOLATED_ARGUMENT_INVALID")
        verify(sys.argv[1])
    except Exception as error:
        allowed = {"ISOLATED_TABLE_SET_MISMATCH", "ISOLATED_FOREIGN_TABLE_REFERENCE",
                   "ISOLATED_ORPHANED_FOREIGN_KEYS", "ISOLATED_FK_NOT_PRESENT",
                   "ISOLATED_SALES_DATA_MISSING", "ISOLATED_RECOVERY_MIGRATION_NOT_PRESENT",
                   "ISOLATED_SQL_QUERY_FAILED", "ISOLATED_FK_METADATA_INVALID",
                   "ISOLATED_ARGUMENT_INVALID"}
        category = str(error) if str(error) in allowed else "ISOLATED_SCOPED_UNCLASSIFIED"
        print("MPW_SCOPED_RESTORE_ABORT=" + category, file=sys.stderr)
        raise SystemExit(1)
