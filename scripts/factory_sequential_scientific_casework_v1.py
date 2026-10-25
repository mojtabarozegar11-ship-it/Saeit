#!/usr/bin/env python3
"""Advance exactly one genuine factory scientific-rework order per invocation.

All evidence is retained privately. A missing source, damaged receipt, absent
independent reviewer or unfinished manuscript remains a blocker, never a pass.
The cursor moves past blocked cases so one impossible source cannot starve 183
other products. It is deliberately separate from the legacy all-order worker.
"""
import argparse
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
from functools import lru_cache
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time

SCHEMA = "saeit.factory.sequential-scientific-casework.v1"
HERE = Path(__file__).resolve().parent
DISK_RESERVE = 2 * 1024 * 1024 * 1024


@lru_cache(maxsize=1)
def engine():
    # The existing VPS deployment uses the installed, pinned basename.
    candidates = (HERE / "license-safe-primary-fulltext-acquisition-sequential-v1.py",
                  HERE / "license-safe-primary-fulltext-acquisition.py",
                  HERE / "factory_primary_fulltext_acquisition_20261024.py")
    path = next((p for p in candidates if p.is_file() and not p.is_symlink()), None)
    if path is None:
        raise RuntimeError("TRUSTED_PRIMARY_SOURCE_WORKER_MISSING")
    spec = importlib.util.spec_from_file_location("saeit_sequential_primary", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def queue(area, m):
    inbox = area / "stage-02/primary-fulltext-repair-inbox"
    m.ensure(inbox.is_dir() and not inbox.is_symlink(), "SOURCE_REWORK_QUEUE_UNAVAILABLE")
    # Keep unsafe, correctly named entries visible: their own turn is blocked.
    names = sorted(p.name for p in inbox.iterdir() if m.NAME.fullmatch(p.name))
    m.ensure(0 < len(names) <= 10000 and len(set(names)) == len(names),
             "CASEWORK_QUEUE_INVALID")
    return names


def cursor_position(path, m, names):
    """Resume after the last identity, not a shifting queue offset.

    Index-only cursors repeat or skip products when earlier entries change.
    Legacy index-only cursor state remains readable.
    """
    if not path.exists() and not path.is_symlink():
        return 0
    record = json.loads(m.safe_read(path, 2048))
    m.ensure(record.get("schema") == SCHEMA and
             type(record.get("next_index")) is int and
             record["next_index"] >= 0, "CASEWORK_CURSOR_INVALID")
    if "last_order_file" in record:
        last = record["last_order_file"]
        m.ensure(isinstance(last, str) and m.NAME.fullmatch(last),
                 "CASEWORK_CURSOR_LAST_ORDER_INVALID")
        return bisect_right(names, last) % len(names)
    return record["next_index"] % len(names)


def source_cycle(m, target, unique, max_attempts, http_get):
    totals = Counter()
    for doi in sorted(unique):
        file = target / "metadata" / (m.key(doi) + ".json")
        if file.exists() or file.is_symlink():
            m.read_verified_evidence(target, doi)
            totals["cached_sources_checked"] += 1
            continue
        if totals["source_attempts"] >= max_attempts:
            totals["source_budget_deferred"] += 1
            continue
        totals["source_attempts"] += 1
        try:
            result, raw, _ = m.evaluate(doi, http_get)
            if raw is not None:
                m.once(target / "licensed-xml" / (m.key(doi) + ".xml"), raw)
            metadata = {"schema":m.SCHEMA, "doi":doi,
                        "doi_key_sha256":m.key(doi),
                        "source_orders":len(unique[doi]),
                        "retrieved_at_utc":datetime.now(timezone.utc).isoformat(),
                        **result,
                        "claim_candidate_assessment":"NOT_SEMANTICALLY_VERIFIED",
                        "qc1000_approved":False,
                        "public_distribution_allowed":False,
                        "independent_scientific_review_completed":False}
            m.once(file, m.canonical(metadata))
            totals["new_source_records"] += 1
            if result["state"] == "LICENSED_FULLTEXT_ARCHIVED":
                totals["new_licensed_sources"] += 1
            else:
                totals["nonlicensed_or_unavailable_sources"] += 1
        except m.TemporaryFailure:
            totals["temporary_provider_failures"] += 1
        except (OSError, ValueError, TypeError, KeyError) as error:
            # Fail this source closed, but allow other sources of this product.
            # Record no invented evidence or review decision.
            totals["blocked_source_attempts"] += 1
            if isinstance(error, m.Blocked) and str(error).startswith("IMMUTABLE_"):
                raise
    return dict(totals)


def step(factory_private, *, max_attempts=4, dry_run=False, http_get=None):
    m = engine()
    if type(max_attempts) is not int or not 0 <= max_attempts <= 20:
        raise ValueError("CASEWORK_SOURCE_BUDGET_INVALID")
    root = Path(factory_private)
    m.ensure(root.is_dir() and not root.is_symlink(), "PRIVATE_FACTORY_UNSAFE")
    area = root / "production-instructions"
    m.ensure(area.is_dir() and not area.is_symlink(), "PRIVATE_INSTRUCTIONS_UNSAFE")
    names = queue(area, m)
    target = area / "stage-02/primary-source-acquisition-v1"
    # Read-only mode must not create the evidence tree or lock.
    cursor = target / ".product-sequential-cursor.json"
    if dry_run:
        index = cursor_position(cursor, m, names)
        return {"schema":SCHEMA, "mode":"read_only", "queue_size":len(names),
                "next_order_file":names[index % len(names)],
                "publications":0, "qc1000_approvals":0}
    storage_free = shutil.disk_usage(root).free
    storage_hold = storage_free < DISK_RESERVE
    if storage_hold:
        max_attempts = 0  # No new XML archives below the factory reserve.
    m.safe_dir(target)
    m.safe_dir(target / "metadata")
    m.safe_dir(target / "licensed-xml")
    lock = target / ".primary-acquisition.lock"
    m.ensure(not lock.is_symlink(), "SOURCE_LOCK_SYMLINK")
    descriptor = os.open(str(lock), os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"schema":SCHEMA, "already_running":True, "cases_processed":0}
        index = cursor_position(cursor, m, names)
        name = names[index]
        started_ns = time.monotonic_ns()
        case = {"schema":SCHEMA, "order_file":name,
                "visited_utc":datetime.now(timezone.utc).isoformat(),
                "result":"BLOCKED_INPUT_INTEGRITY", "source_attempts":0,
                "source_records_available":0, "licensed_sources_available":0,
                "independent_scientific_review_completed":False,
                "manuscript_scientifically_complete":False,
                "qc1000_approved":False, "public_distribution_allowed":False,
                "commercial_release":False, "blocking_code":None,
                "decision":"RETURN_TO_PRODUCTION",
                "stage_owner":"scientific_source_acquisition",
                "required_next_version":"NEW_AUTHENTIC_REVISION_AFTER_REWORK",
                "source_order_sha256":None,
                "source_stage":"NOT_RUN",
                "design_build_package_technical_content_stages":"NOT_RUN_BY_THIS_WORKER",
                "independent_qc_stage":"NOT_PERFORMED"}
        case["storage_reserve_hold"] = storage_hold
        try:
            original = m.safe_read(area / "stage-02/primary-fulltext-repair-inbox" / name)
            case["source_order_sha256"] = hashlib.sha256(original).hexdigest()
            unique, orders, total = m.collect(area, only_order=name)
            m.ensure(len(orders) == 1 and total >= 4, "SELECTED_CASE_EVIDENCE_INVALID")
            report = source_cycle(m, target, unique, max_attempts,
                                  http_get or m.live_get)
            case["source_stage"] = "SOURCE_EVIDENCE_CHECKED"
            case.update(report)
            case["source_tasks"] = total
            case["distinct_doi_count"] = len(unique)
            case["new_claim_candidate_maps"] = m.map_claim_candidates(target, orders)
            m.route_product_rework(target, orders)
            triage_path = target / "stage5-scientific-rework-triage" / name
            triage = json.loads(m.safe_read(triage_path, 2_000_000))
            case["source_attempts"] = report.get("source_attempts", 0)
            case["source_records_available"] = sum(
                (target / "metadata" / (m.key(doi) + ".json")).is_file()
                for doi in unique)
            case["licensed_sources_available"] = triage["licensed_sources_available"]
            if triage["primary_source_acquisition_complete"]:
                case["result"] = "WAITING_QUALIFIED_CLAIM_REVIEW_AND_REAUTHORING"
            elif storage_hold:
                case["result"] = "STORAGE_RESERVE_HOLD_WITH_SOURCE_REWORK_PENDING"
            else:
                case["result"] = "SOURCE_OR_LICENSE_REWORK_REQUIRED"
            case["blocking_code"] = None
        except (OSError, ValueError, RuntimeError, KeyError, TypeError, UnicodeError) as exc:
            # A corrupted product is never accepted; the next product gets its
            # turn rather than allowing this case to freeze the whole queue.
            case["result"] = "BLOCKED_INPUT_INTEGRITY"
            case["blocking_code"] = type(exc).__name__ + ":" + str(exc)[:100]
        case["finished_utc"] = datetime.now(timezone.utc).isoformat()
        case["elapsed_ms"] = round((time.monotonic_ns() - started_ns) / 1_000_000, 3)
        receipt = m.canonical(case)
        receipt_sha256 = hashlib.sha256(receipt).hexdigest()
        # Immutable visit history; per-product status is only a projection.
        history_name = (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                        + "-" + receipt_sha256[:16] + ".json")
        history = (target / "sequential-casework-v1/history"
                   / name.removesuffix(".json") / history_name)
        m.once(history, receipt)
        output = target / "sequential-casework-v1" / name
        m.replace_cursor(output, case)
        m.replace_cursor(cursor, {"schema":SCHEMA, "next_index":index + 1,
                                 "last_order_file":name})
        return {"schema":SCHEMA, "queue_size":len(names),
                "decision":"RETURN_TO_PRODUCTION",
                "source_order_sha256":case["source_order_sha256"],
                "receipt_sha256":receipt_sha256,
                "receipt_relative_path":str(history.relative_to(area)),
                "elapsed_ms":case["elapsed_ms"],
                "cases_processed":1, "selected_order_file":name,
                "next_order_file":names[(index+1) % len(names)],
                "result":case["result"],
                "source_attempts":case["source_attempts"],
                "licensed_sources_available":case["licensed_sources_available"],
                "storage_reserve_hold":storage_hold,
                "blocking_code":case["blocking_code"],
                "qc1000_approvals":0, "publications":0,
                "original_archives_modified":0}
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--max-source-attempts", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(step(args.factory_private, max_attempts=args.max_source_attempts,
                              dry_run=args.dry_run), ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        print("SEQUENTIAL_CASEWORK_ERROR=" + type(exc).__name__ + ":" + str(exc)[:160],
              file=sys.stderr)
        raise SystemExit(1)
