#!/usr/bin/env python3
"""Private shadow-DB-only Stage45 candidate queue bootstrap.

Seeds provisional RESEARCH_REQUIRED entries for previously unpublished
factory-managed products. Product IDs are internal pointers, NOT evidence.
The input historical SQLite is opened query_only; the only writable SQLite
must have the exact dedicated astra-v2-stage45-shadow-<sha>.sqlite3 name.
Never publishes, prices, calls external APIs, updates original products, or
asserts customer demand. Idempotent within a private shadow database.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3

SOURCE_NAME = "factory-fresh-isolated.sqlite3"
TARGET_NAME = re.compile(r"astra-v2-stage45-shadow-[a-f0-9]{12}\.sqlite3\Z")
EXPECTED_MIGRATIONS = (
    "0048_business_market_architecture",
    "0049_astra_stage45_research_queue",
)
EVIDENCE_TARGET = 100
MAX_QUEUE = 3000


def checked(path, expected_name):
    raw = Path(path).expanduser()
    if raw.is_symlink() or not raw.is_file():
        raise ValueError("NO_SYMLINK_OR_MISSING_DB")
    if isinstance(expected_name, str):
        allowed = raw.name == expected_name
    else:
        allowed = expected_name.fullmatch(raw.name) is not None
    if not allowed:
        raise ValueError("REFUSE_NONPRIVATE_DB_NAME")
    return raw.resolve(strict=True)


def rows_from_source(source):
    con = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=20)
    try:
        con.execute("PRAGMA query_only=ON")
        marker = con.execute(
            "SELECT name FROM django_migrations WHERE app='core' "
            "ORDER BY name DESC LIMIT 1"
        ).fetchone()
        if marker != (EXPECTED_MIGRATIONS[0],):
            raise ValueError("SOURCE_NOT_0048")
        records = con.execute(
            "SELECT id FROM core_product WHERE factory_managed=1 AND active=0 ORDER BY id"
        ).fetchall()
        if len(records) > MAX_QUEUE or any(
            type(row[0]) is not int or row[0] < 1 for row in records
        ):
            raise ValueError("SOURCE_OUTSIDE_BOUNDS")
        return [row[0] for row in records]
    finally:
        con.close()


def prepare(source_path, shadow_path):
    source = checked(source_path, SOURCE_NAME)
    shadow = checked(shadow_path, TARGET_NAME)
    if source.parent != shadow.parent or source == shadow:
        raise ValueError("ONLY_SIBLING_PRIVATE_SNAPSHOT_ALLOWED")
    source_ids = rows_from_source(source)
    db = sqlite3.connect(shadow, timeout=15)
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        marker = db.execute(
            "SELECT name FROM django_migrations WHERE app='core' "
            "ORDER BY name DESC LIMIT 1"
        ).fetchone()
        if marker != (EXPECTED_MIGRATIONS[1],):
            raise ValueError("TARGET_NOT_0049")
        present = db.execute(
            "SELECT key,kind,status,evidence_verified_independently,"
            "build_authorized,publish_authorized,payment_authorized "
            "FROM core_factoryqueueitem ORDER BY id"
        ).fetchall()
        if any(
            kind != "discovery" or status != "RESEARCH_REQUIRED"
            or any(flag != 0 for flag in (verified,build,publish,payment))
            or not re.fullmatch(r"research:legacy-product:[0-9]{1,16}",key or "")
            for key,kind,status,verified,build,publish,payment in present
        ):
            raise ValueError("NONRESEARCH_QUEUE_OR_AUTHORIZATION_DETECTED")
        allowed_keys = {"research:legacy-product:" + str(pk) for pk in source_ids}
        if any(row[0] not in allowed_keys for row in present):
            raise ValueError("UNRELATED_SHADOW_QUEUE_RECORD_DETECTED")
        for pk in source_ids:
            db.execute(
                "INSERT OR IGNORE INTO core_factoryqueueitem "
                "(created_at,updated_at,key,kind,status,priority_score,"
                "evidence_verified_independently,build_authorized,"
                "publish_authorized,payment_authorized) "
                "VALUES (CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,?,"
                "'discovery','RESEARCH_REQUIRED',NULL,0,0,0,0)",
                ("research:legacy-product:"+str(pk),)
            )
        keys = [row[0] for row in db.execute(
            "SELECT key FROM core_factoryqueueitem ORDER BY key"
        )]
        if len(keys) != len(source_ids) or set(keys) != allowed_keys:
            raise ValueError("SHADOW_QUEUE_COVERAGE_INCOMPLETE")
        if db.execute("SELECT COUNT(*) FROM core_discoverysnapshot").fetchone()[0] != 0:
            raise ValueError("UNVALIDATED_SHADOW_EVIDENCE_PRESENT")
        if db.execute(
            "SELECT COUNT(*) FROM core_factoryqueueitem "
            "WHERE kind!='discovery' OR status!='RESEARCH_REQUIRED' "
            "OR priority_score IS NOT NULL "
            "OR evidence_verified_independently != 0 "
            "OR build_authorized != 0 OR publish_authorized != 0 "
            "OR payment_authorized != 0"
        ).fetchone()[0]:
            raise ValueError("COMMERCIAL_RELEASE_GUARD_FAILED")
        db.commit()
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    if rows_from_source(source) != source_ids:
        raise ValueError("HISTORICAL_INPUT_CHANGED_CONCURRENTLY")
    return {
        "mode": "private_shadow_0049_research_only",
        "topics_needing_independent_research": len(source_ids),
        "verified_customer_demand": 0,
        "independently_verified_evidence_in_shadow": 0,
        "evidence_target_per_candidate": EVIDENCE_TARGET,
        "commercial_quality_scores_assigned": 0,
        "live_database_mutations": 0,
        "public_releases": 0,
        "payments_enabled": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--shadow", required=True)
    args = parser.parse_args()
    report = prepare(args.source, args.shadow)
    print("ASTRA_0049_PRIVATE_SHADOW_RESEARCH_QUEUE=PASS")
    print("ASTRA_0049_PRIVATE_RESEARCH_TOPICS="+str(
        report["topics_needing_independent_research"]))
    print("ASTRA_0049_LIVE_DB_WRITES=0")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
