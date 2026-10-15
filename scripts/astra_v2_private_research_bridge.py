#!/usr/bin/env python3
"""Private standalone, order-free Astra research bridge (Python 3.8+).

Reads existing original-factory SQLite strictly in mode=ro/query_only and
stores ID-only, provisional research hypotheses in an unrelated private SQLite.
No Django, HTTP, order events, product builder, site or payment connections.
Runs safely as a bounded idempotent tick from one independent VPS cron row.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

MAX_BATCH = 50
REQUIRED = {
    "core_product": {"id", "factory_managed", "active"},
    "core_factoryrun": {"id", "product_id"},
    "core_researchproject": {"id", "factory_run_id"},
    "core_researchsource": {"id", "project_id"},
    "core_evidence": {"id", "project_id", "source_id"},
}
QUERY = """
 SELECT p.id, COUNT(DISTINCT s.id) AS source_refs,
        COUNT(DISTINCT e.id) AS evidence_refs
 FROM core_product p
 LEFT JOIN core_factoryrun r ON r.product_id=p.id
 LEFT JOIN core_researchproject rp ON rp.factory_run_id=r.id
 LEFT JOIN core_researchsource s ON s.project_id=rp.id
 LEFT JOIN core_evidence e ON e.project_id=rp.id AND e.source_id=s.id
 WHERE p.factory_managed=1 AND p.active=0 AND p.id>?
 GROUP BY p.id ORDER BY p.id LIMIT ?
"""
SCHEMA = """
 CREATE TABLE IF NOT EXISTS research_tasks (
   key TEXT PRIMARY KEY,
   legacy_product_id INTEGER NOT NULL UNIQUE CHECK(legacy_product_id>0),
   stage TEXT NOT NULL DEFAULT 'WAITING_FOR_EVIDENCE'
     CHECK(stage IN ('WAITING_FOR_EVIDENCE','REVIEW_REQUIRED','REJECTED')),
   source_refs_unverified INTEGER NOT NULL CHECK(source_refs_unverified>=0),
   evidence_refs_unverified INTEGER NOT NULL CHECK(evidence_refs_unverified>=0),
   market_demand_verified INTEGER NOT NULL DEFAULT 0 CHECK(market_demand_verified=0),
   sale_ready INTEGER NOT NULL DEFAULT 0 CHECK(sale_ready=0),
   quality_score INTEGER CHECK(quality_score IS NULL),
   created_utc TEXT NOT NULL,
   updated_utc TEXT NOT NULL
 );
 CREATE TABLE IF NOT EXISTS bridge_meta(
   key TEXT PRIMARY KEY,
   value TEXT NOT NULL
 );
"""


def source_path(filename):
    p = Path(filename).expanduser()
    if p.is_symlink() or not p.is_file() or not p.stat().st_size:
        raise ValueError("SOURCE_DB_MISSING_OR_SYMLINK")
    return p.resolve(strict=True)


def private_path(filename, original):
    p = Path(filename).expanduser()
    if p.is_symlink() or p.name == "" or p.suffix != ".sqlite3":
        raise ValueError("PRIVATE_DB_PATH_NOT_ALLOWED")
    if not p.parent.is_dir() or p.parent.is_symlink():
        raise ValueError("PRIVATE_DB_PARENT_MISSING_OR_SYMLINK")
    candidate = p.resolve(strict=False)
    if candidate == original or candidate.parent == original.parent:
        raise ValueError("PRIVATE_DB_MUST_BE_IN_SEPARATE_DIRECTORY")
    if p.exists() and (not p.is_file() or not p.stat().st_size):
        raise ValueError("PRIVATE_DB_INVALID")
    return candidate


def open_source(path):
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10)
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, columns in REQUIRED.items():
            if table not in names:
                raise ValueError("SOURCE_SCHEMA_MISSING_" + table)
            fields = {r[1] for r in db.execute("PRAGMA table_info(" + table + ")")}
            if not columns.issubset(fields):
                raise ValueError("SOURCE_COLUMNS_MISSING_" + table)
        return db
    except BaseException:
        db.close()
        raise


def _meta(db, key, default="0"):
    row = db.execute("SELECT value FROM bridge_meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def read_tasks(original, after_id, limit):
    with open_source(original) as src:
        rows = src.execute(QUERY, (after_id, limit)).fetchall()
        wrapped = False
        if not rows and after_id > 0:
            rows = src.execute(QUERY, (0, limit)).fetchall()
            wrapped = True
        src.execute("COMMIT")
    return rows, wrapped


def _utc():
    return datetime.now(timezone.utc).isoformat()


def tick(original, private, limit=25, *, check=False):
    if not (1 <= limit <= MAX_BATCH):
        raise ValueError("BATCH_LIMIT_OUT_OF_RANGE")
    src = source_path(original)
    out = private_path(private, src)
    if check:
        if not out.is_file():
            raise ValueError("PRIVATE_BRIDGE_NOT_INSTALLED")
        with sqlite3.connect(out.as_uri() + "?mode=ro", uri=True, timeout=10) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            tables = {r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"research_tasks", "bridge_meta"}.issubset(tables):
                raise ValueError("PRIVATE_BRIDGE_SCHEMA_MISSING")
            count = db.execute("SELECT COUNT(*) FROM research_tasks").fetchone()[0]
            wrong = db.execute(
                "SELECT COUNT(*) FROM research_tasks WHERE "
                "market_demand_verified<>0 OR sale_ready<>0 OR quality_score IS NOT NULL"
            ).fetchone()[0]
            if wrong:
                raise ValueError("PRIVATE_BRIDGE_UNSAFE_RELEASE_FLAG")
            last = _meta(db, "last_tick_utc", "")
            cursor = int(_meta(db, "cursor_id"))
            db.execute("COMMIT")
        with open_source(src) as ro:
            ro.execute("COMMIT")
        return {
            "mode": "READ_ONLY_HEALTH",
            "research_tasks": count, "last_tick_utc": last, "cursor_id": cursor,
            "source_opened_read_only": True,
            "commercially_qualified": 0, "products_for_sale": 0,
        }

    lock = out.parent / ".astra-research-bridge.lock"
    if lock.is_symlink():
        raise ValueError("UNSAFE_PRIVATE_LOCK")
    fd = os.open(str(lock), os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"mode": "SKIPPED_ALREADY_RUNNING", "new_research_tasks": 0,
                    "commercially_qualified": 0}
        created = not out.exists()
        db = sqlite3.connect(str(out), timeout=10)
        try:
            if created:
                os.chmod(str(out), 0o600)
            db.execute("PRAGMA busy_timeout=10000")
            db.executescript(SCHEMA)
            existing = {r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"research_tasks", "bridge_meta"}.issubset(existing):
                raise ValueError("PRIVATE_SCHEMA_UNEXPECTED")
            cursor = int(_meta(db, "cursor_id"))
            rows, wrapped = read_tasks(src, cursor, limit)
            new = updated = 0
            timestamp = _utc()
            db.execute("BEGIN IMMEDIATE")
            try:
                for pid, sources, evidence in rows:
                    key = "legacy-factory-product:{}".format(int(pid))
                    cur = db.execute(
                        """INSERT OR IGNORE INTO research_tasks
                        (key, legacy_product_id, source_refs_unverified,
                         evidence_refs_unverified, created_utc, updated_utc)
                        VALUES (?,?,?,?,?,?)""",
                        (key, int(pid), int(sources), int(evidence),
                         timestamp, timestamp))
                    if cur.rowcount:
                        new += 1
                    else:
                        update = db.execute(
                            """UPDATE research_tasks
                            SET source_refs_unverified=?,
                                evidence_refs_unverified=?, updated_utc=?
                            WHERE key=? AND stage='WAITING_FOR_EVIDENCE'
                              AND (source_refs_unverified<>? OR evidence_refs_unverified<>?)""",
                            (int(sources), int(evidence), timestamp, key,
                             int(sources), int(evidence)))
                        updated += update.rowcount
                next_cursor = int(rows[-1][0]) if rows else 0
                for key, val in (
                    ("cursor_id", str(next_cursor)),
                    ("last_tick_utc", timestamp),
                    ("ticks_total", str(int(_meta(db, "ticks_total")) + 1)),
                ):
                    db.execute("INSERT OR REPLACE INTO bridge_meta(key,value) VALUES(?,?)",
                               (key, val))
                db.commit()
            except BaseException:
                db.rollback()
                raise
            return {
                "mode": "PRIVATE_ORDER_FREE_TICK", "scanned": len(rows),
                "new_research_tasks": new, "updated_count_only": updated,
                "total_research_tasks": db.execute(
                    "SELECT COUNT(*) FROM research_tasks").fetchone()[0],
                "cursor_id": next_cursor, "wrapped": wrapped,
                "source_opened_read_only": True, "customer_orders_needed": False,
                "commercially_qualified": 0, "products_for_sale": 0,
                "publication_authorized": False, "payment_activated": False,
            }
        finally:
            db.close()
    finally:
        os.close(fd)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-db", required=True)
    ap.add_argument("--research-db", required=True)
    ap.add_argument("--limit", type=int, default=25)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true")
    group.add_argument("--check", action="store_true")
    args = ap.parse_args()
    result = tick(args.source_db, args.research_db, args.limit, check=args.check)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
