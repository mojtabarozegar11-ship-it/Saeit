#!/usr/bin/env python3
"""Read-only bridge from deployed Astra/Research SQLite to Astra 2.0 selection.

This program never fetches the web, modifies the database or authorizes a
factory build. All candidates are locally supplied: no automatic inference of
a buyer problem, rights, economic score, or willingness to pay from keywords.

Supported data:
* current ResearchProject -> ResearchSource -> Evidence attached to an exact
  product via FactoryRun (uncategorized only; cannot imply buying demand);
* optional Astra 0049 FactoryQueueItem -> DiscoverySnapshot with a specifically
  typed, time-stamped, SHA-256-digested claim (provisional and unverified).
The output is PRIVATE review-only and contains no raw evidence passages.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "astra_selector_bridge_target", str(HERE / "astra_opportunity_selector.py"))
_selector = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_selector)

MAX_CANDIDATES = 300
MAX_REFS_PER_CANDIDATE = 40


def _table(conn, name):
    if not re.fullmatch(r"core_[a-z0-9_]+", name):
        raise ValueError("table not allowlisted")
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _columns(conn, name):
    if not _table(conn, name):
        return set()
    return {row[1] for row in conn.execute("PRAGMA table_info(" + name + ")")}


def _requirements(conn, table, columns):
    return set(columns).issubset(_columns(conn, table))


def _django_sqlite_utc_timestamp(raw):
    """Read Django USE_TZ=True SQLite DateTimeField as UTC, never as server local.

    Django SQLite stores UTC timestamps without a numeric offset. Only its
    precise SQL timestamp format is upgraded; arbitrary naive ISO strings
    remain invalid and are rejected by the independent selector's age gate.
    """
    if not isinstance(raw, str):
        return raw
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{1,6})?", raw):
        return raw
    try:
        return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return raw


def _references(conn, candidates):
    outputs = []
    audit = {
        "legacy_references_examined": 0,
        "legacy_references_review_only": 0,
        "astra_snapshots_examined": 0,
        "astra_snapshots_eligible": 0,
        "bridge_writes_to_factory": 0,
    }
    legacy = all(_requirements(conn, table, fields) for table, fields in (
        ("core_product", ("id", "active", "factory_managed")),
        ("core_factoryrun", ("id", "product_id")),
        ("core_researchproject", ("id", "factory_run_id")),
        ("core_researchsource", ("id", "project_id", "url", "content_hash")),
        ("core_evidence", ("id", "project_id", "source_id")),
    ))
    astra = all(_requirements(conn, table, fields) for table, fields in (
        ("core_factoryqueueitem", ("id", "key", "kind")),
        ("core_discoverysnapshot", (
            "id", "hypothesis_id", "url", "content_hash", "retrieved_at", "record")),
    ))
    audit["legacy_schema_available"] = legacy
    audit["astra_0049_schema_available"] = astra

    for c in candidates:
        key = c["opportunity_key"]
        product_id = c.get("product_id")
        queue_key = c.get("astra_queue_key")
        if product_id is not None:
            if type(product_id) is not int or product_id < 1:
                raise ValueError("product_id must be a positive integer")
            if not legacy:
                audit.setdefault("legacy_schema_missing_count", 0)
                audit["legacy_schema_missing_count"] += 1
            else:
                # Link evidence to exactly this factory-managed, inactive product.
                # Never import sources from other projects or website catalog rows.
                q = """
                  SELECT s.id, s.url, s.content_hash
                  FROM core_product AS p
                  JOIN core_factoryrun AS run ON run.product_id=p.id
                  JOIN core_researchproject AS proj ON proj.factory_run_id=run.id
                  JOIN core_researchsource AS s ON s.project_id=proj.id
                  WHERE p.id=? AND p.factory_managed=1 AND p.active=0
                    AND EXISTS (
                      SELECT 1 FROM core_evidence e
                      WHERE e.source_id=s.id AND e.project_id=proj.id
                    )
                  ORDER BY s.id LIMIT ?
                """
                rows = conn.execute(q, (product_id, MAX_REFS_PER_CANDIDATE)).fetchall()
                for row in rows:
                    audit["legacy_references_examined"] += 1
                    # A citation and opaque content_hash are not attestations.
                    # Without a verified claim classifier this never enters the
                    # selector's categorized market-evidence snapshot set.
                    audit["legacy_references_review_only"] += 1
        if queue_key is not None:
            if not isinstance(queue_key, str) or not re.fullmatch(
                r"[A-Za-z0-9_.:-]{1,100}", queue_key
            ):
                raise ValueError("invalid astra_queue_key")
            if not astra:
                audit.setdefault("astra_schema_missing_count", 0)
                audit["astra_schema_missing_count"] += 1
            else:
                rows = conn.execute(
                    """SELECT s.id, s.url, s.content_hash, s.retrieved_at, s.record
                       FROM core_factoryqueueitem q
                       JOIN core_discoverysnapshot s ON s.hypothesis_id=q.id
                       WHERE q.key=? AND q.kind='discovery'
                       ORDER BY s.id LIMIT ?""",
                    (queue_key, MAX_REFS_PER_CANDIDATE),
                ).fetchall()
                for row in rows:
                    audit["astra_snapshots_examined"] += 1
                    try:
                        record = json.loads(row["record"]) if isinstance(
                            row["record"], str) else row["record"]
                        if not isinstance(record, dict):
                            continue
                        # Synthetic/illustrative markers must survive the
                        # SQLite-to-selector boundary, not be silently dropped.
                        if _selector._explicitly_synthetic(record):
                            audit["astra_snapshots_synthetic_rejected"] = (
                                audit.get("astra_snapshots_synthetic_rejected", 0) + 1
                            )
                            continue
                        # The ORIGINAL captured record must explicitly classify
                        # its claim; do not derive commercial intent from prose.
                        claim = record.get("claim_type")
                        if claim not in _selector.CLAIM_TYPES:
                            continue
                        candidate = {
                            "opportunity_key": key,
                            "url": row["url"],
                            "content_sha256": row["content_hash"],
                            "observed_at": _django_sqlite_utc_timestamp(row["retrieved_at"]),
                            "claim_type": claim,
                        }
                        # Malformed or stale records are excluded in the selector.
                        outputs.append(candidate)
                        audit["astra_snapshots_eligible"] += 1
                    except (ValueError, TypeError, KeyError):
                        continue
    return outputs, audit


def evaluate_db(database, candidates, now_utc):
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        raise ValueError("candidate batch exceeds read-only bridge limit")
    seen = set()
    for c in candidates:
        key, _, _, _ = _selector._check_candidate(c)
        if key in seen:
            raise ValueError("duplicate opportunity_key")
        seen.add(key)
    raw_db = Path(database).expanduser()
    if raw_db.is_symlink():
        raise ValueError("database symlink not permitted")
    db = raw_db.resolve(strict=True)
    if not db.is_file():
        raise ValueError("unsafe database path")
    # A read-only SQLite transaction obtains a consistent snapshot; query_only
    # forbids SQL changes. Uses parameterized SQL and an exact table allowlist.
    uri = db.as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        try:
            refs, audit = _references(conn, candidates)
            output = _selector.rank_opportunities(candidates, refs, now_utc)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    output["adapter"] = "astra_sqlite_read_only"
    output["bridge_audit"] = audit
    # No real-money or publish authorization, even if a record declares
    # its own demand class or the selector returns REVIEW_REQUIRED.
    assert all(
        not item["build_authorized"] and not item["publish_authorized"]
        for item in output["candidates"]
    )
    return output


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="Existing SQLite database (read only)")
    ap.add_argument("--candidates", required=True, help="Private local JSON candidate list")
    ap.add_argument("--out", required=True, help="Private local review report")
    ap.add_argument("--now-utc", required=True)
    args = ap.parse_args(argv)
    raw_source = Path(args.candidates).expanduser()
    if raw_source.is_symlink():
        raise ValueError("candidate input symlink not permitted")
    source = raw_source.resolve(strict=True)
    if not source.is_file() or source.stat().st_size > 2_000_000:
        raise ValueError("unsafe candidates file")
    doc = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("candidate JSON must be object")
    result = evaluate_db(args.db, doc["candidates"], args.now_utc)
    dest = Path(args.out).resolve()
    if dest == source or dest == Path(args.db).resolve() or dest.is_symlink():
        raise ValueError("refuse overwriting database or candidate inputs")
    if not dest.parent.is_dir():
        raise ValueError("output directory must exist")
    fd, staging = tempfile.mkstemp(prefix=".astra-evidence-", dir=str(dest.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(staging, 0o600)
        os.replace(staging, dest)
    finally:
        if os.path.exists(staging):
            os.unlink(staging)
    print("ASTRA_EVIDENCE_BRIDGE_READ_ONLY=true")
    print("ASTRA_EVIDENCE_CANDIDATES=" + str(len(result["candidates"])))
    print("ASTRA_EVIDENCE_BUILD_AUTHORIZED=false")
    print("ASTRA_EVIDENCE_PUBLICATION_AUTHORIZED=false")


if __name__ == "__main__":
    main()
