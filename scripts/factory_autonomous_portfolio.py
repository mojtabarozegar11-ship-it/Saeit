#!/usr/bin/env python3
"""Independent VPS-local opportunity/product preparation — NEVER order-triggered.

Checks all factory-managed draft products in rotating bounded batches.
Produces private, idempotent evidence dossiers and quality-action queues only.
Does not read customer orders, charge accounts, call an LLM, activate products,
or publish to a marketplace. Python 3.8+.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

HERE = Path(__file__).resolve().parent
PILOT_FILE = HERE / "first-product-pilot.py"
if not PILOT_FILE.is_file():
    PILOT_FILE = HERE.parent / "scripts" / "factory_first_product_pilot.py"
spec = importlib.util.spec_from_file_location("saeit_factory_product_pilot", str(PILOT_FILE))
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)

quality_spec = importlib.util.spec_from_file_location(
    "saeit_factory_evidence_quality", str(HERE / "factory_evidence_quality.py")
)
quality = importlib.util.module_from_spec(quality_spec)
quality_spec.loader.exec_module(quality)


def select_product_ids(conn, previous_id=0, limit=25):
    """Product creation/research drives production; orders have no involvement."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(core_product)")}
    required = {"id", "active", "factory_managed"}
    if not required.issubset(columns):
        raise RuntimeError("FACTORY_PRODUCT_SCHEMA_INCOMPATIBLE")
    # Never rewrite already listed products. Do not process unrelated store items.
    ids = [row[0] for row in conn.execute(
        "SELECT id FROM core_product WHERE factory_managed=1 AND active=0 ORDER BY id"
    )]
    if not ids:
        return []
    after = next((i for i, item in enumerate(ids) if item > previous_id), 0)
    ids = ids[after:] + ids[:after]
    return ids[:limit]


def read_cursor(path):
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        return max(0, int(state.get("last_product_id", 0)))
    except (FileNotFoundError, ValueError, TypeError, KeyError):
        return 0


def persist_product(bundle, root):
    ident = int(bundle["product_id"])
    folder = root / ("product-" + str(ident))
    data = json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2)
    digest = hashlib.sha256(data.encode("utf-8")).hexdigest()
    marker = folder / "sha256.txt"
    if (marker.is_file()
            and (folder / "evidence_manifest.json").is_file()
            and (folder / "internal_draft.md").is_file()
            and marker.read_text(encoding="utf-8").strip() == digest):
        return False, digest
    pilot.write_atomic(folder / "evidence_manifest.json", data + "\n")
    pilot.write_atomic(folder / "internal_draft.md", pilot.draft_markdown(bundle))
    pilot.write_atomic(marker, digest + "\n")
    return True, digest


def build(db, out, limit):
    """One bounded autonomous pass; local DB is opened as read-only."""
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    root = Path(out).expanduser().resolve()
    database = Path(db).expanduser().resolve()
    if not database.is_file():
        raise RuntimeError("FACTORY_DATABASE_MISSING")
    state_path = root / "autonomous-state.json"
    previous_id = read_cursor(state_path)
    conn = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        product_ids = select_product_ids(conn, previous_id, limit)
        products = [pilot.prepare(conn, i) for i in product_ids]
    finally:
        conn.close()
    updated, unchanged = 0, 0
    entries = []
    for bundle in products:
        changed, digest = persist_product(bundle, root)
        updated += int(changed)
        unchanged += int(not changed)
        issues = bundle["issues"]
        research_gate = quality.assess(bundle)
        entries.append({
            "product_id": bundle["product_id"],
            "sha256": digest,
            "quality_blocker_count": len(issues),
            "missing_validation_factors": len(bundle["missing_factors"]),
            "evidence_count": len(bundle["evidence"]),
            "source_count": len(bundle["sources"]),
            "stage": "needs_more_evidence" if issues else "internal_review_pending",
            "customer_order_required": False,
            "research_quality_gate": research_gate,
            "publish_authorized": False,
        })
    next_cursor = product_ids[-1] if product_ids else previous_id
    portfolio = {
        "mode": "supply_led_autonomous",
        "trigger": "vps_local_schedule_or_factory_product_changes",
        "depends_on_customer_orders": False,
        "processed_count": len(products),
        "updated_count": updated,
        "unchanged_count": unchanged,
        "entries": entries,
        "research_review_candidates": sum(
            int(x["research_quality_gate"]["research_gate_passed"]) for x in entries
        ),
        "publishable_product_count": 0,
        "quality_policy_version": "saeit.factory.research-readiness.v1",
        "publication_requires_qa_and_owner_authorization": True,
    }
    # No timestamps: unchanged inputs leave a stable output and consume no API.
    serialized = json.dumps(portfolio, ensure_ascii=False, sort_keys=True, indent=2)
    target = root / "autonomous-portfolio.json"
    if not target.is_file() or target.read_text(encoding="utf-8") != serialized + "\n":
        pilot.write_atomic(target, serialized + "\n")
    if product_ids:
        pilot.write_atomic(state_path, json.dumps(
            {"last_product_id": next_cursor}, sort_keys=True
        ) + "\n")
    return portfolio


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args(argv)
    outcome = build(args.db, args.out, args.limit)
    print("AUTONOMOUS_FACTORY_ORDER_DEPENDENCY=false")
    print("AUTONOMOUS_FACTORY_PRODUCTS_PROCESSED=" + str(outcome["processed_count"]))
    print("AUTONOMOUS_FACTORY_DOSSIERS_CREATED_OR_UPDATED=" + str(outcome["updated_count"]))
    print("AUTONOMOUS_FACTORY_DOSSIERS_UNCHANGED=" + str(outcome["unchanged_count"]))
    print("AUTONOMOUS_FACTORY_PRIVATE_QA_ONLY=true")
    print("AUTONOMOUS_FACTORY_PUBLICATION_NOT_AUTHORIZED=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
