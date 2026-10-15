#!/usr/bin/env python3
"""Clone-only SQLite 0048->0049 proof with real backup/restore parity.

Never writes to its input database. A strict exact filename and sibling
scratch directory guard forbid running against a live DB path. This validates
restoring a disposable SNAPSHOT copy, not an operational production restore.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3

SOURCE_NAME = "factory-fresh-isolated.sqlite3"
WORK_PREFIX = "astra0049-restore-proof-"
LEGACY_TABLES = (
    "core_product", "core_factoryrun", "core_researchsource", "core_evidence"
)
MIGRATION = "0049_astra_stage45_research_queue"


def safe_path(path):
    p = Path(path).expanduser()
    if p.is_symlink():
        raise ValueError("SYMLINK_NOT_ALLOWED")
    return p.resolve(strict=True)


def read_state(db):
    conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=15)
    try:
        conn.execute("PRAGMA query_only=ON")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError("SQLITE_INTEGRITY_FAILED")
        versions = conn.execute(
            "SELECT name FROM django_migrations WHERE app='core' ORDER BY name DESC LIMIT 1"
        ).fetchone()
        table_counts = {
            table: conn.execute("SELECT count(*) FROM " + table).fetchone()[0]
            for table in LEGACY_TABLES
        }
        flag = conn.execute(
            "SELECT count(*) FROM django_migrations "
            "WHERE app='core' AND name=?", (MIGRATION,)
        ).fetchone()[0]
        return versions, table_counts, flag
    finally:
        conn.close()


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def prove(source_path, ddl_path, scratch_path):
    raw_source = Path(source_path).expanduser()
    raw_scratch = Path(scratch_path).expanduser()
    source, ddl, scratch = map(safe_path, (source_path, ddl_path, scratch_path))
    if (
        raw_source.name != SOURCE_NAME
        or source.name != SOURCE_NAME
        or raw_scratch.name[:len(WORK_PREFIX)] != WORK_PREFIX
        or scratch.name[:len(WORK_PREFIX)] != WORK_PREFIX
        or scratch.parent != source.parent
        or not source.is_file() or not ddl.is_file() or not scratch.is_dir()
        or ddl == source or scratch == source or ddl.is_symlink()
    ):
        raise ValueError("COPY_ONLY_SOURCE_AND_SIBLING_WORKSPACE_REQUIRED")
    for child in scratch.iterdir():
        raise ValueError("FRESH_EMPTY_WORKSPACE_REQUIRED")
    statements = ddl.read_text(encoding="utf-8")
    lowered = statements.lower()
    if (
        len(statements) > 100_000
        or "create table" not in lowered
        or "core_factoryqueueitem" not in lowered
        or "core_discoverysnapshot" not in lowered
        or re.search(r"\b(drop|delete|update|alter|attach|detach|replace|truncate|vacuum)\b", lowered)
    ):
        raise ValueError("REJECT_NONADDITIVE_0049_DDL")

    baseline_sha = digest(source)
    version_before, counts_before, flag_before = read_state(source)
    if version_before != ("0048_business_market_architecture",) or flag_before:
        raise ValueError("ONLY_KNOWN_0048_SNAPSHOT_SUPPORTED")

    backup = scratch / "offline-backup.sqlite3"
    upgraded = scratch / "upgrade-probe.sqlite3"
    restored = scratch / "restore-probe.sqlite3"
    original = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=15)
    try:
        original.execute("PRAGMA query_only=ON")
        dest = sqlite3.connect(backup)
        try:
            original.backup(dest)
        finally:
            dest.close()
    finally:
        original.close()

    backup_sha = digest(backup)
    assert read_state(backup) == (version_before, counts_before, flag_before)
    shutil.copyfile(backup, upgraded)

    db = sqlite3.connect(upgraded)
    try:
        db.executescript(statements)
        db.execute(
            "INSERT INTO django_migrations (app,name,applied) "
            "VALUES ('core', ?, CURRENT_TIMESTAMP)", (MIGRATION,)
        )
        db.commit()
        tables = {
            row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not {"core_factoryqueueitem","core_discoverysnapshot"} <= tables:
            raise ValueError("0049_TABLES_MISSING_AFTER_MIGRATION")
        if read_state(upgraded)[1] != counts_before:
            raise ValueError("LEGACY_ROW_COUNTS_CHANGED")
        db.execute(
            "INSERT INTO core_factoryqueueitem "
            "(created_at,updated_at,key,kind,status,build_authorized,"
            "publish_authorized,payment_authorized,evidence_verified_independently) "
            "VALUES (CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'discovery:restore-test',"
            "'discovery','RESEARCH_REQUIRED',0,0,0,0)"
        )
        db.commit()
        try:
            db.execute(
                "UPDATE core_factoryqueueitem SET publish_authorized=1 "
                "WHERE key='discovery:restore-test'"
            )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
        else:
            raise ValueError("UNVERIFIED_PUBLICATION_UPDATE_SUCCEEDED")
    finally:
        db.close()

    shutil.copyfile(backup, restored)
    restored_sha = digest(restored)
    if backup_sha != restored_sha:
        raise ValueError("RESTORE_BACKUP_BYTES_MISMATCH")
    if read_state(restored) != (version_before, counts_before, flag_before):
        raise ValueError("RESTORED_0048_STATE_MISMATCH")
    if digest(source) != baseline_sha:
        raise ValueError("ORIGINAL_SNAPSHOT_CHANGED")
    return {
        "snapshot_backup_restored_exactly": True,
        "migration_tested_on_disposable_clone": True,
        "input_snapshot_unchanged": True,
        "historical_counts_preserved": True,
        "publication_without_verified_research_blocked": True,
        "live_database_migrations": 0,
        "scheduled_worker_changes": 0,
        "public_product_releases": 0,
        "payments_attempted": 0,
        "restored_0048_marker": True,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True)
    p.add_argument("--ddl", required=True)
    p.add_argument("--workspace", required=True)
    a = p.parse_args()
    report = prove(a.source, a.ddl, a.workspace)
    print("ASTRA_0049_OFFLINE_BACKUP_RESTORE=PASS")
    print("ASTRA_0049_LIVE_FACTORY_MUTATIONS=0")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
