#!/usr/bin/env python3
"""Read-only, schema-tolerant proof of the legacy factory / Astra V2 boundary.

Inspects only two explicitly supplied SQLite databases; no migrations, Django
initialization, site access, secrets, network calls or mutation. Prints aggregate
counts only: no evidence text, URLs, user data or business transaction rows.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

LEGACY = {
    "core_product": {"id", "factory_managed", "active"},
    "core_factoryrun": {"id", "product_id"},
    "core_researchproject": {"id", "factory_run_id"},
    "core_researchsource": {"id", "project_id", "url", "content_hash"},
    "core_evidence": {"id", "source_id", "project_id"},
}
ASTRA_0049 = {
    "core_factoryqueueitem": {"id", "key", "kind"},
    "core_discoverysnapshot": {
        "id", "hypothesis_id", "url", "content_hash", "retrieved_at", "record",
    },
}
V2 = {"jobs": {"id", "builder", "stage", "artifact_sha"}}
SHA = re.compile(r"[a-fA-F0-9]{64}\Z")


def safe_db(path):
    p = Path(path).expanduser()
    if p.is_symlink() or not p.is_file():
        raise ValueError("database missing or symlink")
    p = p.resolve(strict=True)
    if not p.stat().st_size:
        raise ValueError("database empty")
    return p


def tables(conn):
    return {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def columns(conn, table):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", table):
        raise ValueError("table name outside safe alphabet")
    return {row[1] for row in conn.execute("PRAGMA table_info(" + table + ")")}


def schema_check(conn, definitions):
    names = tables(conn)
    return {
        name: {
            "present": name in names,
            "required_columns_present": name in names and
            fields.issubset(columns(conn, name)),
            "missing_required_columns": sorted(
                fields - columns(conn, name)) if name in names else sorted(fields),
        }
        for name, fields in definitions.items()
    }


def read_factory(conn):
    legacy = schema_check(conn, LEGACY)
    stage45 = schema_check(conn, ASTRA_0049)
    migration = {
        "django_migration_tracking_present": False,
        "latest_core_migration": None,
        "astra_0049_recorded": False,
    }
    if ("django_migrations" in tables(conn) and
            {"app", "name"}.issubset(columns(conn, "django_migrations"))):
        migration["django_migration_tracking_present"] = True
        migration["latest_core_migration"] = conn.execute(
            "SELECT MAX(name) FROM django_migrations WHERE app='core'").fetchone()[0]
        migration["astra_0049_recorded"] = (
            conn.execute(
                "SELECT COUNT(*) FROM django_migrations "
                "WHERE app='core' AND name LIKE '0049_%'"
            ).fetchone()[0] > 0)
    has_legacy = all(x["required_columns_present"] for x in legacy.values())
    has_0049 = all(x["required_columns_present"] for x in stage45.values())
    totals = {}
    for table in LEGACY:
        if legacy[table]["required_columns_present"]:
            totals[table] = conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
        else:
            totals[table] = None
    if legacy["core_product"]["required_columns_present"]:
        totals["private_factory_managed_drafts"] = conn.execute(
            "SELECT COUNT(*) FROM core_product "
            "WHERE factory_managed=1 AND active=0").fetchone()[0]
    else:
        totals["private_factory_managed_drafts"] = None
    if legacy["core_researchsource"]["required_columns_present"] and \
            legacy["core_evidence"]["required_columns_present"]:
        totals["source_rows_linked_to_evidence"] = conn.execute(
            "SELECT COUNT(*) FROM core_researchsource s "
            "WHERE EXISTS (SELECT 1 FROM core_evidence e "
            "WHERE e.source_id=s.id AND e.project_id=s.project_id)").fetchone()[0]
    else:
        totals["source_rows_linked_to_evidence"] = None
    return {
        "legacy_readonly_adapter_schema_compatible": has_legacy,
        "stage45_schema_tables_present": has_0049,
        "migration": migration,
        "schema": {"legacy": legacy, "astra_0049": stage45},
        "aggregates": totals,
        "real_market_demand_independently_attested": False,
        "stage45_cutover_authorized": False,
    }


def read_private(conn):
    schema = schema_check(conn, V2)
    if not schema["jobs"]["required_columns_present"]:
        return {
            "schema": schema, "families_qa_passed": None,
            "jobs_by_stage": {}, "technical_queue_compatible": False,
        }
    return {
        "schema": schema,
        "technical_queue_compatible": True,
        "families_qa_passed": conn.execute(
            "SELECT COUNT(DISTINCT builder) FROM jobs "
            "WHERE stage='PRIVATE_QA_PASSED'").fetchone()[0],
        "jobs_by_stage": {
            state: count for state, count in conn.execute(
                "SELECT stage,COUNT(*) FROM jobs GROUP BY stage ORDER BY stage")
        },
    }


def analyze(factory_db, private_db):
    f = safe_db(factory_db)
    p = safe_db(private_db)
    if f == p:
        raise ValueError("independent factory databases required")
    with sqlite3.connect(f.as_uri() + "?mode=ro", uri=True, timeout=10) as original:
        original.execute("PRAGMA query_only=ON")
        original.execute("BEGIN")
        factory = read_factory(original)
        original.execute("COMMIT")
    with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True, timeout=10) as private:
        private.execute("PRAGMA query_only=ON")
        private.execute("BEGIN")
        v2 = read_private(private)
        private.execute("COMMIT")
    return {
        "schema_version": 1, "mode": "strictly_read_only_stage45_inventory",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "legacy_factory": factory, "isolated_astra_v2": v2,
        "bridge_in_place": False,
        "new_commercial_products_verified": 0,
        "factory_database_writes": 0,
        "private_database_writes": 0,
        "site_mutations": 0, "payments_activated": False,
        "next_gate": (
            "RECONCILE_CODE_SCHEMA_MIGRATIONS_BEFORE_DISPOSABLE_COPY_TEST"
            if not factory["stage45_schema_tables_present"] or
               not factory["migration"]["astra_0049_recorded"]
            else "VERIFY_CODE_AND_STAGING_MIGRATION_WITH_INDEPENDENT_TESTS"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factory-db", required=True)
    parser.add_argument("--private-db", required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.factory_db, args.private_db),
                     ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
