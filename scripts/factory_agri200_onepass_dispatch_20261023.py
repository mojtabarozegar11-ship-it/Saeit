#!/usr/bin/env python3
"""Bounded, evidence-preserving one-pass dispatch for 200 agricultural orders.

Runs already-installed private factory workers in dependency order. It NEVER
creates a commercial approval, a customer order, or a public site listing.
Only an independently verifiable finished product may enter a storefront.
"""
import argparse
import collections
import fcntl
import json
from pathlib import Path
import re
import subprocess
import sys

ORDER_NAME = re.compile(r"WO-[0-9]{8}--r001\.json\Z")
STAGES = (
    ("outside_literature_scout", "stage2-literature-scout.py", 110,
     ("--batch", "6", "--workers", "1", "--query-burst", "1")),
    ("scientific_research", "stage2-research.py", 105,
     ("--batch", "250")),
    ("bilingual_design_and_prototype", "stage34-autonomous-handoff.py", 105,
     ("--batch", "250")),
    ("private_workbook_draft", "stage5-evidence-workbook.py", 105,
     ("--batch", "250")),
    ("technical_preflight_and_rework", "stage6-preflight-rework.py", 105,
     ("--batch", "250")),
    ("source_specific_revision_brief", "stage5-substantive-rework.py", 105,
     ("--batch", "250")),
)


def indexed_orders(root):
    index = root / "production-instructions/owner-agri200-p0-index.json"
    if index.is_symlink() or not index.is_file():
        raise RuntimeError("AGRI200_INDEX_MISSING")
    payload = json.loads(index.read_text(encoding="utf8"))
    names = payload.get("order_ids_ranked")
    if (payload.get("topic_count") != 200 or
            payload.get("edition_goal_count") != 400 or
            not isinstance(names, list) or len(names) != 200 or
            len(set(names)) != 200 or
            any(not ORDER_NAME.fullmatch(str(n) + "--r001.json") for n in names)):
        raise RuntimeError("AGRI200_INDEX_INTEGRITY_FAILED")
    return [n + "--r001.json" for n in names]


def intake_integrity(root, names):
    """Verify historical indexed orders survive the authorized cleanup."""
    folder = root / "production-instructions/orders"
    count = {"indexed": len(names), "valid": 0, "missing": 0, "invalid": 0}
    for source_name in names:
        ident = source_name.removesuffix("--r001.json")
        path = folder / (ident + ".json")
        if not path.exists() and not path.is_symlink():
            count["missing"] += 1
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 250000:
            count["invalid"] += 1
            continue
        try:
            order = json.loads(path.read_text(encoding="utf8"))
            if (not isinstance(order, dict) or order.get("id") != ident
                    or order.get("status") not in ("issued", "in_engineering",
                        "blocked_rework", "completed_verified")
                    or not re.fullmatch(r"[0-9a-f]{64}",
                        str(order.get("fingerprint", "")))):
                raise ValueError("AGRI200_ORDER_INVALID")
        except (OSError, ValueError, TypeError):
            count["invalid"] += 1
            continue
        count["valid"] += 1
    count["ready"] = count["valid"] == count["indexed"]
    return count


def inventory(root, names):
    area = root / "production-instructions"
    # These are progress artifacts, NEVER equivalent to sale approval.
    probes = {
        "stage2_researched": "stage-02/receipts",
        "stage3_designed": "stage-03/receipts",
        "stage4_prototyped": "stage-04/receipts",
        "stage5_drafted": "stage-05/completed-drafts",
        "stage6_technical_preflight": "stage-06/technical-preflight",
        "stage5_rework_briefs": "stage-05/substantive-revision-manifests",
        "stage6_independent_review_requests": "stage-06/substantive-review-inbox",
    }
    result = {k: sum((area / directory / name).is_file() and
                     not (area / directory / name).is_symlink()
                     for name in names) for k, directory in probes.items()}
    result.update({"internal_orders": 200, "planned_language_editions": 400,
                   "storefront_release_verified": False,
                   "customer_delivery_verified": False})
    # A technical preflight explicitly does not authorize stage seven.
    return result


def evidence_gaps(root, names):
    area = root / "production-instructions"
    status_file = area / "stage-02/literature-scout-status.json"
    result = {"unresearched_orders": 0, "missing_bibliography": 0,
              "gap_classes": {}}
    if status_file.is_file() and not status_file.is_symlink():
        status = json.loads(status_file.read_text(encoding="utf8"))
        for key in ("openalex_key_configured", "provider_cooldown_active",
                    "external_provider_unavailable", "attempted_this_run",
                    "still_require_manual_or_external_research"):
            result[key] = status.get(key)
    counts = collections.Counter()
    for rank, name in enumerate(names, 1):
        if (area / "stage-02/receipts" / name).is_file():
            continue
        result["unresearched_orders"] += 1
        paper = area / "stage-02/literature-candidates" / (
            "AGRI-%03d--r001.json" % rank)
        if paper.is_symlink() or not paper.is_file():
            result["missing_bibliography"] += 1
            continue
        try:
            packet = json.loads(paper.read_text(encoding="utf8"))
            reason = packet.get("evidence_gap_reason", "unclassified")
            if not isinstance(reason, str) or not re.fullmatch(r"[a-z0-9_]{1,90}", reason):
                reason = "unclassified"
            counts[reason] += 1
        except (OSError, ValueError, TypeError):
            counts["unreadable_workpaper"] += 1
    result["gap_classes"] = dict(sorted(counts.items()))
    return result


def worker_command(root, ops, label, filename, batch):
    py = ops.parent.parent / ".venv/bin/python"
    if not py.is_file() or not py.stat().st_mode & 0o111:
        raise RuntimeError("AGRI200_VENV_MISSING")
    worker = ops / filename
    if worker.is_symlink() or not worker.is_file():
        raise RuntimeError("AGRI200_WORKER_MISSING:" + filename)
    command = [str(py), "-B", str(worker), "--factory-private", str(root)]
    if label == "outside_literature_scout":
        command += ["--stage2-program", str(ops / "stage2-research.py")]
    elif label == "technical_preflight_and_rework":
        command += ["--stage34-worker", str(ops / "stage34-autonomous-handoff.py"),
                    "--stage5-worker", str(ops / "stage5-evidence-workbook.py")]
    elif label == "private_workbook_draft":
        command += ["--stage34-worker", str(ops / "stage34-autonomous-handoff.py")]
    elif label == "source_specific_revision_brief":
        command += ["--stage34-worker", str(ops / "stage34-autonomous-handoff.py"),
                    "--stage5-worker", str(ops / "stage5-evidence-workbook.py"),
                    "--stage6-worker", str(ops / "stage6-preflight-rework.py")]
    return command + list(batch)


def dispatch(root, ops, *, run_workers=True):
    root, ops = Path(root).resolve(), Path(ops).resolve()
    if not root.is_dir() or not ops.is_dir():
        raise RuntimeError("AGRI200_FACTORY_PATH_INVALID")
    names = indexed_orders(root)
    initial = inventory(root, names)
    intake = intake_integrity(root, names)
    outcomes = {}
    if run_workers and intake["ready"]:
        lock = ops / ".agri200-dispatch.lock"
        if lock.is_symlink():
            raise RuntimeError("AGRI200_UNSAFE_LOCK")
        with lock.open("a+b") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            for label, filename, seconds, args in STAGES:
                # Use installed workers' own locks; they remain the source of truth.
                try:
                    command = worker_command(root, ops, label, filename, args)
                    completed = subprocess.run(command, stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE,
                                               timeout=seconds, check=False)
                    outcomes[label] = ("ok" if completed.returncode == 0
                                       else "error_exit_" + str(completed.returncode))
                except subprocess.TimeoutExpired:
                    outcomes[label] = "timeout"
                except (OSError, RuntimeError) as exc:
                    outcomes[label] = "error_" + type(exc).__name__
    final = inventory(root, names)
    advanced = any(final[k] > initial[k] for k in initial
                   if k.startswith("stage") and isinstance(initial[k], int))
    failed = any(status != "ok" for status in outcomes.values())
    if not run_workers:
        production_outcome = "audit_only"
        safe_next_action = "run_authorized_workers"
    elif not intake["ready"]:
        production_outcome = "blocked_incomplete_stage1_intake"
        safe_next_action = "reconcile_valid_current_work_orders_before_regeneration"
    elif failed:
        production_outcome = "worker_failure"
        safe_next_action = "inspect_worker_errors_before_retry"
    elif advanced:
        production_outcome = "internal_progress_verified"
        safe_next_action = "continue_evidence_and_quality_review"
    else:
        production_outcome = "blocked_no_progress"
        safe_next_action = "investigate_evidence_rework_and_approval_gates"
    return {"schema": "saeit.factory.agri200.onepass-dispatch.v1",
            "before": initial, "after": final, "worker_results": outcomes,
            "intake_integrity": intake,
            "production_outcome": production_outcome,
            "safe_next_action": safe_next_action,
            "workers_success_does_not_mean_products_completed": True,
            "remaining_research_diagnostics": evidence_gaps(root, names),
            "automated_factory_progress_confirmed": advanced,
            "finished_products_published_by_this_dispatch": 0,
            "why_no_unverified_release": "stage6_review_and_full_specific_manuscript_missing",
            "public_sites_modified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--operations", required=True)
    parser.add_argument("--audit-only", action="store_true")
    a = parser.parse_args()
    try:
        print(json.dumps(dispatch(a.factory_private, a.operations,
                                  run_workers=not a.audit_only),
                         sort_keys=True, ensure_ascii=False), flush=True)
    except Exception as exc:
        print("AGRI200_DISPATCH_ERROR=" + type(exc).__name__ + ":" +
              str(exc)[:120], file=sys.stderr)
        sys.exit(1)
