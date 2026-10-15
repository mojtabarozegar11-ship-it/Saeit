#!/usr/bin/env python3
"""VPS-aligned 0048 factory research-gap inventory without altering live state.

Connects read-only to the legacy database; outputs private numeric-ID-only
research actions for existing unpublished factory-managed products. Source and
evidence row counts are NOT independently validated, market demand or sales.
No external network, no migrations, no SQL writes, no credential discovery.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile

MAX_PRODUCTS = 2000
EVIDENCE_TARGET = 100
TABLE_FIELDS = {
    "core_product": {"id","factory_managed","active"},
    "core_factoryrun": {"id","product_id"},
    "core_researchproject": {"id","factory_run_id"},
    "core_researchsource": {"id","project_id"},
    "core_evidence": {"id","source_id","project_id"},
}


def inventory(path):
    original = Path(path).expanduser()
    if original.is_symlink() or not original.is_file() or original.stat().st_size > 600_000_000:
        raise ValueError("missing, symlinked or oversized legacy factory database")
    db = original.resolve(strict=True)
    conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=12)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        actual = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        for table, required in TABLE_FIELDS.items():
            if table not in actual:
                raise ValueError("legacy factory schema unavailable")
            columns = {r[1] for r in conn.execute("PRAGMA table_info("+table+")")}
            if not required.issubset(columns):
                raise ValueError("legacy schema required columns missing")
        if "django_migrations" not in actual:
            raise ValueError("untracked factory schema")
        last = conn.execute(
            "SELECT name FROM django_migrations WHERE app='core' "
            "ORDER BY name DESC LIMIT 1").fetchone()
        if not last or not last[0].startswith(("0048_", "0049_")):
            raise ValueError("must use known VPS-aligned factory schema")
        total = conn.execute(
            "SELECT COUNT(*) FROM core_product WHERE factory_managed=1 AND active=0"
        ).fetchone()[0]
        if total > MAX_PRODUCTS:
            raise ValueError("too many unpublished factory products")
        rows = conn.execute("""
            SELECT p.id,
                   COUNT(DISTINCT CASE WHEN e.id IS NOT NULL THEN s.id END)
                       AS directly_linked_source_rows,
                   COUNT(DISTINCT CASE WHEN e.id IS NOT NULL THEN e.id END)
                       AS evidence_rows
            FROM core_product AS p
            LEFT JOIN core_factoryrun AS r ON r.product_id=p.id
            LEFT JOIN core_researchproject AS rp ON rp.factory_run_id=r.id
            LEFT JOIN core_researchsource AS s ON s.project_id=rp.id
            LEFT JOIN core_evidence AS e
                ON e.source_id=s.id AND e.project_id=rp.id
            WHERE p.factory_managed=1 AND p.active=0
            GROUP BY p.id ORDER BY p.id
        """).fetchall()
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    if len(rows)!=total:
        raise ValueError("inconsistent factory product count")
    actions = []
    for product_id, sources, evidence in rows:
        if not isinstance(product_id,int) or product_id<1 or sources<0 or evidence<0:
            raise ValueError("invalid legacy counts")
        actions.append({
            "internal_product_id": product_id,
            "phase": "RESEARCH_REQUIRED",
            "preliminary_linked_source_rows": sources,
            "preliminary_evidence_rows": evidence,
            "independently_verified_evidence_items": 0,
            "independent_evidence_target": EVIDENCE_TARGET,
            "commercial_quality_score": None,
            "customer_willingness_to_pay_verified": False,
            "factory_build_authorized": False,
            "public_sale_authorized": False,
            "next_actions": [
                "VALIDATE_PROBLEM_WITH_ACTUAL_ELIGIBLE_BUYERS",
                "VERIFY_EVIDENCE_PROVENANCE_RIGHTS_AND_RECENCY",
                "BENCHMARK_AGAINST_COMPETING_FREE_PRODUCTS",
                "ASSEMBLE_100_INDEPENDENTLY_CHECKED_EVIDENCE_ITEMS",
                "REQUIRE_INDEPENDENT_EXPERT_PRODUCT_QA",
            ],
        })
    actions.sort(key=lambda row: (
        -row["preliminary_linked_source_rows"],row["internal_product_id"]))
    return {
        "schema_version": 1,
        "mode": "legacy_0048_read_only_no_order_research_inventory",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_unpublished_factory_managed_products": total,
        "linked_source_rows_counted": sum(r["preliminary_linked_source_rows"] for r in actions),
        "products_with_at_least_one_linked_source": sum(
            bool(r["preliminary_linked_source_rows"]) for r in actions),
        "independently_verified_commercial_products": 0,
        "publications_approved": 0,
        "real_customer_demand_claims": 0,
        "factory_database_writes": 0,
        "public_site_changes": 0,
        "payment_operations": 0,
        "network_calls": 0,
        "worklist": actions,
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args(argv)
    src=Path(args.db).resolve(strict=True)
    dst=Path(args.out).expanduser()
    if dst.is_symlink() or not dst.parent.is_dir():
        raise ValueError("unsafe private report location")
    dst=dst.resolve()
    if src==dst or dst.suffix!=".json":
        raise ValueError("read-only database cannot be overwritten")
    result=inventory(args.db)
    serialized=json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    if len(serialized)>1_000_000:
        raise ValueError("research inventory too large")
    fd, name=tempfile.mkstemp(prefix=".astra45-legacy-gap-",dir=str(dst.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name,0o600)
        os.replace(name,dst)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    print("ASTRA_LEGACY_RESEARCH_WORKLIST_ITEMS="+str(len(result["worklist"])))
    print("ASTRA_LEGACY_RESEARCH_INDEPENDENT_COMMERCIAL_SCORE=UNSET")
    print("ASTRA_LEGACY_FACTORY_DATABASE_WRITES=0")


if __name__=="__main__":
    main()
