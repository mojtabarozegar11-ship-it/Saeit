#!/usr/bin/env python3
"""Read-only Astra stage-4/5 research backlog: NO demand, quality or sale claims.

This tool is an internal no-order research scheduler input, not a source
fetcher or product manufacturer. Inputs are only an existing 0049 SQLite queue.
All observations remain preliminary even when 100 references are present.
Does not mutate databases, publish, assign sale prices, or use credentials.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

HERE = Path(__file__).resolve().parent
CLAIMS = ("problem", "willingness_to_pay", "comparison", "feasibility")
EVIDENCE_TARGET_PER_PRODUCT = 100
MAX_QUEUE_ITEMS = 2000
MAX_SNAPSHOTS = 10000
MAX_OUTPUT_BYTES = 4_000_000


def _import_file(name):
    file = HERE / (name + ".py")
    if not file.is_file() or file.is_symlink():
        raise ValueError("trusted stage45 module missing")
    spec = importlib.util.spec_from_file_location("astra45_" + name, str(file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_only_conn(db):
    path = Path(db).expanduser()
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 400_000_000:
        raise ValueError("database is missing, symlinked or oversized")
    resolved = path.resolve(strict=True)
    conn = sqlite3.connect(resolved.as_uri() + "?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _check_schema(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    required = {
        "core_factoryqueueitem": {"id", "key", "kind", "status", "priority_score",
                                  "build_authorized", "publish_authorized",
                                  "payment_authorized", "evidence_verified_independently"},
        "core_discoverysnapshot": {"id", "hypothesis_id", "url", "content_hash",
                                   "retrieved_at", "record"},
        "django_migrations": {"app", "name"},
    }
    for table, needed in required.items():
        if table not in tables:
            raise ValueError("0049 schema required: " + table)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(" + table + ")")}
        if not needed.issubset(cols):
            raise ValueError("incompatible 0049 schema: " + table)
    migrated = conn.execute(
        "SELECT COUNT(*) FROM django_migrations WHERE app='core' "
        "AND name='0049_astra_stage45_research_queue'"
    ).fetchone()[0]
    if migrated != 1:
        raise ValueError("0049 migration marker not present")


def _typed_reference(row, now, selector, adapter):
    if not isinstance(row["record"], str):
        return None
    try:
        record = json.loads(row["record"])
        if not isinstance(record, dict):
            return None
        claim = record.get("claim_type")
        if claim not in CLAIMS or selector._explicitly_synthetic(record):
            return None
        url = row["url"]
        host = selector._public_https_domain(url)
        digest = row["content_hash"]
        if not host or not isinstance(digest, str) or not re.fullmatch(
            r"[a-fA-F0-9]{64}", digest):
            return None
        when = adapter._django_sqlite_utc_timestamp(row["retrieved_at"])
        seen = selector._utc(when)
        if not now-timedelta(days=selector.MAX_SNAPSHOT_AGE_DAYS) <= seen <= now:
            return None
        return host, claim, digest.lower()
    except (ValueError, TypeError, OverflowError):
        return None


def analyze(db, now_utc):
    selector = _import_file("astra_opportunity_selector")
    adapter = _import_file("astra_research_evidence_adapter")
    now = selector._utc(now_utc)
    with _read_only_conn(db) as conn:
        conn.execute("BEGIN")
        try:
            _check_schema(conn)
            rowcount = conn.execute("SELECT COUNT(*) FROM core_factoryqueueitem").fetchone()[0]
            evidencecount = conn.execute("SELECT COUNT(*) FROM core_discoverysnapshot").fetchone()[0]
            if rowcount > MAX_QUEUE_ITEMS or evidencecount > MAX_SNAPSHOTS:
                raise ValueError("research batch outside bounded limits")
            topics = conn.execute(
                "SELECT id,key,kind,status,priority_score,build_authorized,"
                "publish_authorized,payment_authorized,evidence_verified_independently "
                "FROM core_factoryqueueitem ORDER BY id"
            ).fetchall()
            snapshots = conn.execute(
                "SELECT hypothesis_id,url,content_hash,retrieved_at,record "
                "FROM core_discoverysnapshot ORDER BY id"
            ).fetchall()
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # Group on exact content rather than row ID, URL or claim. A document
    # mirrored under different hosts is not independent corroboration.
    by_topic_digest = defaultdict(lambda: defaultdict(set))
    row_occurrences = defaultdict(int)
    invalid = 0
    topic_ids = {r["id"] for r in topics}
    for row in snapshots:
        if row["hypothesis_id"] not in topic_ids:
            invalid += 1
            continue
        ref = _typed_reference(row, now, selector, adapter)
        if ref is None:
            invalid += 1
            continue
        host, claim, digest = ref
        key = (row["hypothesis_id"], digest)
        by_topic_digest[key[0]][key[1]].add((host, claim))
        row_occurrences[key] += 1

    eligible = defaultdict(dict)
    mirrored_excluded = 0
    same_content_collapsed = 0
    for topic_id, digests in by_topic_digest.items():
        for digest, references in digests.items():
            occurrences = row_occurrences[(topic_id, digest)]
            if len({host for host, _ in references}) > 1:
                # Exclude *all* conflicting mirrors regardless of row order.
                mirrored_excluded += occurrences
                continue
            eligible[topic_id][digest] = references
            same_content_collapsed += occurrences - 1

    work = []
    for row in topics:
        if not isinstance(row["key"], str) or not re.fullmatch(
            r"[A-Za-z0-9_.:-]{1,100}", row["key"]):
            raise ValueError("invalid queue identity")
        if row["kind"] != "discovery":
            continue
        # Database-level invariants: abort on any self-promoted source record.
        if (row["status"] != "RESEARCH_REQUIRED" or any(
                row[field] != 0 for field in (
                    "build_authorized", "publish_authorized",
                    "payment_authorized", "evidence_verified_independently"))):
            raise ValueError("research-only authorization invariant violated")
        unique_documents = eligible[row["id"]]
        kinds = {claim for entries in unique_documents.values()
                 for _, claim in entries}
        domains = {host for entries in unique_documents.values()
                   for host, _ in entries}
        gaps = [claim for claim in CLAIMS if claim not in kinds]
        tasks = ["COLLECT_AND_INDEPENDENTLY_VALIDATE_" + claim.upper()
                 for claim in gaps]
        if len(domains) < 3:
            tasks.append("FIND_AT_LEAST_THREE_DISTINCT_PRELIMINARY_SOURCE_DOMAINS")
        if len(unique_documents) < EVIDENCE_TARGET_PER_PRODUCT:
            tasks.append("BUILD_100_ITEM_INDEPENDENTLY_CHECKED_EVIDENCE_DOSSIER")
        tasks.append("OBTAIN_REAL_CUSTOMER_AND_EXPERT_VALIDATION")
        tasks.append("COMPARE_WITH_FREE_COMPETITORS_BEFORE_PRICING")
        # No recognized independent attestation exists in schema 0049:
        # complete URLs/claims only mean a candidate can be manually reviewed.
        work.append({
            "key": row["key"],
            "stored_status": row["status"],
            "preliminary_priority_score": (
                float(row["priority_score"]) if row["priority_score"] is not None else None),
            "preliminary_unique_references": len(unique_documents),
            "preliminary_distinct_hosts": len(domains),
            "preliminary_claims": sorted(kinds),
            "missing_claims": gaps,
            "evidence_target": EVIDENCE_TARGET_PER_PRODUCT,
            "next_research_actions": tasks,
            "market_demand_independently_verified": False,
            "commercial_quality_score": None,
            "build_authorized": False,
            "publish_authorized": False,
            "payment_authorized": False,
        })
    work.sort(key=lambda r: (
        len(r["missing_claims"]), -r["preliminary_unique_references"], r["key"]))
    return {
        "schema_version": 1,
        "mode": "private_read_only_no_order_research_backlog",
        "observed_utc": now.isoformat(),
        "queue_items_examined": len(topics),
        "discovery_topics": len(work),
        "snapshot_rows_examined": len(snapshots),
        "invalid_or_unusable_snapshots": invalid + mirrored_excluded,
        "mirrored_snapshot_rows_excluded": mirrored_excluded,
        "same_content_snapshot_rows_collapsed": same_content_collapsed,
        "verified_market_demand_topics": 0,
        "commercially_released_products": 0,
        "factory_mutations": 0,
        "network_calls": 0,
        "payment_attempts": 0,
        "backlog": work,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--now-utc", required=True)
    a = p.parse_args(argv)
    source = Path(a.db).resolve(strict=True)
    dest = Path(a.output).expanduser()
    if dest.is_symlink() or not dest.parent.is_dir():
        raise ValueError("unsafe destination")
    dest = dest.resolve()
    if source == dest or dest.suffix != ".json":
        raise ValueError("refuse overwriting database / non-JSON output")
    result = analyze(a.db, a.now_utc)
    output = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if len(output.encode()) > MAX_OUTPUT_BYTES:
        raise ValueError("output exceeds bounded limit")
    fd, scratch = tempfile.mkstemp(prefix=".astra45-backlog-", dir=str(dest.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(output)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(scratch, 0o600)
        os.replace(scratch, dest)
    finally:
        if os.path.exists(scratch):
            os.unlink(scratch)
    print("ASTRA_STAGE45_PRIVATE_BACKLOG_TOPICS=" + str(len(result["backlog"])))
    print("ASTRA_STAGE45_COMMERCIAL_RELEASE_AUTHORIZED=false")


if __name__ == "__main__":
    main()
