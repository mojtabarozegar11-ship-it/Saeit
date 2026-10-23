#!/usr/bin/env python3
"""VPS-local, continuously repeated and fail-closed agricultural production loop.

The local cron/watchdog is the scheduler; GitHub is only the deployment bridge.
Every tick consumes the current source/rework evidence, runs genuine workers in
dependency order, rechecks new candidates and records an immutable-QC summary.
Never invent scientific validation, reviews, orders, or public releases.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

SCHEMA = "saeit.factory.agri200.autonomous-closed-loop.v1"
NAME = re.compile(r"WO-[0-9]{8}--r[0-9]{3}\.json\Z")
ORDER = re.compile(r"WO-[0-9]{8}\Z")
# Separate failures may not halt any other worker. Installed workers have
# their own cursor, safety checks and revision-bound immutable receipts.
STAGES = (
    ("source_discovery", "stage2-literature-scout.py", 110,
     ("--batch", "6", "--workers", "1", "--query-burst", "1")),
    ("source_validation", "stage2-research.py", 105, ("--batch", "250")),
    ("design_and_prototype", "stage34-autonomous-handoff.py", 105, ("--batch", "250")),
    ("bilingual_manuscript", "stage5-evidence-workbook.py", 105, ("--batch", "250")),
    ("technical_preflight", "stage6-preflight-rework.py", 105, ("--batch", "250")),
    ("source_specific_repair", "stage5-substantive-rework.py", 105, ("--batch", "250")),
    ("source_grounded_reauthoring", "agri200-source-grounded-v003.py", 105, ("--batch", "250")),
    ("candidate_rebuild", "research-navigator.py", 105, ("--batch", "250")),
    ("strict_independent_qc1000", "agri200-strict-qc1000.py", 105, ("--batch", "250")),
    ("v003_independent_mechanical_qc", "agri200-source-grounded-v003-qc.py", 105, ("--batch", "250")),
)


def indexed_orders(area):
    index = area / "owner-agri200-p0-index.json"
    if index.is_symlink() or not index.is_file():
        raise RuntimeError("P0_INDEX_MISSING")
    data = json.loads(index.read_text(encoding="utf-8"))
    names = data.get("order_ids_ranked")
    if (data.get("topic_count") != 200 or data.get("edition_goal_count") != 400
            or not isinstance(names, list) or len(names) != 200
            or len(set(names)) != 200 or any(
                not isinstance(name, str) or not ORDER.fullmatch(name)
                for name in names)):
        raise RuntimeError("P0_INDEX_INVALID")
    return names


def count_artifacts(area, folder):
    path = area / folder
    if path.is_symlink() or not path.is_dir():
        return 0
    return sum(item.is_file() and not item.is_symlink() and NAME.fullmatch(item.name) is not None
               for item in path.iterdir())


def qc_rework_facts(area):
    path = area / "stage-05/strict-qc-rework"
    issues = Counter()
    actions = Counter()
    if path.is_symlink() or not path.is_dir():
        return {"tickets": 0, "findings": {}, "repair_route": {}}
    tickets = 0
    for item in path.iterdir():
        if not item.is_file() or item.is_symlink() or not NAME.fullmatch(item.name):
            continue
        tickets += 1
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
            if data.get("must_resubmit_new_artifact_and_repeat_strict_qc") is not True:
                actions["invalid_ticket_needs_attention"] += 1
                continue
            for finding in data.get("critical_findings", []):
                if not isinstance(finding, str):
                    continue
                if "CANDIDATE_NOT_BUILT" in finding or "INTEGRITY" in finding:
                    actions["technical_repackage_or_integrity_repair"] += 1
                elif "SOURCE" in finding or "FULLTEXT" in finding:
                    actions["source_research_required"] += 1
                elif "MANUSCRIPT" in finding or "METHODS_ONLY" in finding:
                    actions["original_manuscript_rewrite_required"] += 1
                elif "EXPERT" in finding or "SIGNED" in finding or "CERTIFIED" in finding:
                    actions["authentic_external_specialist_required"] += 1
                elif "LEGAL" in finding or "RIGHTS" in finding:
                    actions["distribution_rights_review_required"] += 1
                issues[finding.split(":", 1)[0][:100]] += 1
        except (OSError, ValueError, TypeError):
            actions["invalid_ticket_needs_attention"] += 1
    return {"tickets": tickets, "findings": dict(issues.most_common(12)),
            "repair_route": dict(sorted(actions.items()))}


def snapshot(area):
    return {
        "stage2_sources": count_artifacts(area, "stage-02/receipts"),
        "stage3_designs": count_artifacts(area, "stage-03/receipts"),
        "stage4_prototypes": count_artifacts(area, "stage-04/receipts"),
        "stage5_manuscripts": count_artifacts(area, "stage-05/completed-drafts"),
        "stage5_repair_briefs": count_artifacts(area, "stage-05/substantive-revision-manifests"),
        "stage5_candidate_archives": count_artifacts(area, "stage-05/downloadable-receipts"),
        "stage5_source_grounded_v003": count_artifacts(area, "stage-05/source-grounded-v003-manifests"),
        "stage6_source_grounded_v003_mechanical_qc": count_artifacts(area, "stage-06/source-grounded-v003-qc"),
        "stage6_preflights": count_artifacts(area, "stage-06/technical-preflight"),
        "stage6_strict_qc": count_artifacts(area, "stage-06/strict-qc1000"),
        "stage5_returned_to_rework": count_artifacts(area, "stage-05/strict-qc-rework"),
        "new_revision_artifacts": sum(
            1 for p in (area / "stage-05/completed-drafts").iterdir()
            if p.is_file() and not p.is_symlink() and NAME.fullmatch(p.name)
            and not p.name.endswith("--r001.json")
        ) if (area / "stage-05/completed-drafts").is_dir()
        and not (area / "stage-05/completed-drafts").is_symlink() else 0,
    }


def missing_orders(area, folder, orders):
    """Actual order coverage, not a misleading count of revision files."""
    location = area / folder
    if location.is_symlink() or not location.is_dir():
        return list(orders)
    present = {
        item.name.split("--r", 1)[0]
        for item in location.iterdir()
        if item.is_file() and not item.is_symlink()
        and NAME.fullmatch(item.name)
    }
    return [order for order in orders if order not in present]


def previous_stalls(path):
    """Read only our own prior status, bounded and fail-closed for symlinks."""
    if path.is_symlink():
        raise RuntimeError("AUTONOMOUS_STATUS_SYMLINK")
    if not path.exists():
        return 0
    if not path.is_file() or path.stat().st_size > 200000:
        raise RuntimeError("AUTONOMOUS_STATUS_INVALID")
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError):
        return 0
    if previous.get("schema") != SCHEMA:
        return 0
    count = previous.get("consecutive_no_progress_ticks", 0)
    return min(9999, max(0, count)) if isinstance(count, int) else 0


def worker_command(root, ops, label, filename, args):
    py = ops.parent.parent / ".venv/bin/python"
    script = ops / filename
    if not py.is_file() or not os.access(py, os.X_OK):
        raise RuntimeError("VENV_MISSING")
    if script.is_symlink() or not script.is_file():
        raise RuntimeError("WORKER_NOT_INSTALLED")
    command = [str(py), "-B", str(script), "--factory-private", str(root)]
    stage34 = str(ops / "stage34-autonomous-handoff.py")
    stage5 = str(ops / "stage5-evidence-workbook.py")
    if label == "source_discovery":
        command += ["--stage2-program", str(ops / "stage2-research.py")]
    elif label == "bilingual_manuscript":
        command += ["--stage34-worker", stage34]
    elif label in ("technical_preflight", "candidate_rebuild", "strict_independent_qc1000"):
        command += ["--stage34-worker", stage34, "--stage5-worker", stage5]
    elif label == "source_grounded_reauthoring":
        command += ["--stage34-worker", stage34, "--stage5-worker", stage5,
                    "--candidate-worker", str(ops / "research-navigator.py")]
    elif label == "v003_independent_mechanical_qc":
        command += ["--stage34-worker", stage34]
    elif label == "source_specific_repair":
        command += ["--stage34-worker", stage34, "--stage5-worker", stage5,
                    "--stage6-worker", str(ops / "stage6-preflight-rework.py")]
    if label == "strict_independent_qc1000":
        command += ["--criteria", str(ops / "agri200-strict-qc-catalog.json")]
    return command + list(args)


def save_atomic(path, payload):
    if path.is_symlink():
        raise RuntimeError("UNSAFE_STATUS_LINK")
    fd, name = tempfile.mkstemp(prefix=".autonomous-loop-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def run_tick(root, ops, *, workers=True, invoke=None):
    root = Path(root).resolve()
    ops = Path(ops).resolve()
    area = root / "production-instructions"
    if not area.is_dir() or area.is_symlink() or not ops.is_dir() or ops.is_symlink():
        raise RuntimeError("FACTORY_ROOT_UNSAFE")
    orders = indexed_orders(area)
    if len(orders) != 200:
        raise RuntimeError("ORDER_COUNT_INVALID")
    state = area / "stage-06"
    if state.is_symlink() or not state.is_dir():
        raise RuntimeError("STAGE6_STATE_MISSING")
    lock_path = ops / ".agri200-autonomous-loop.lock"
    if lock_path.is_symlink():
        raise RuntimeError("UNSAFE_LOOP_LOCK")
    with lock_path.open("a+b") as stream:
        os.fchmod(stream.fileno(), 0o600)
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"schema": SCHEMA, "already_running": True}
        before = snapshot(area)
        results = {}
        if workers:
            runner = invoke or subprocess.run
            for label, filename, seconds, args in STAGES:
                try:
                    command = worker_command(root, ops, label, filename, args)
                    outcome = runner(command, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, timeout=seconds, check=False)
                    results[label] = ("ok" if outcome.returncode == 0
                                      else "worker_exit_%d" % outcome.returncode)
                except subprocess.TimeoutExpired:
                    results[label] = "timeout_requeued_next_tick"
                except (OSError, RuntimeError, ValueError) as exc:
                    results[label] = "worker_error_" + type(exc).__name__
        after = snapshot(area)
        diffs = {key: after[key] - before[key] for key in before}
        errors = sum(result != "ok" for result in results.values())
        real_progress = any(increment > 0 for increment in diffs.values())
        prior_stalls = previous_stalls(state / "autonomous-closed-loop-status.json") if workers else 0
        consecutive_stalls = 0 if real_progress else prior_stalls + int(workers)
        awaiting_sources = missing_orders(area, "stage-02/receipts", orders)
        awaiting_revisions = missing_orders(area, "stage-05/source-grounded-v003-manifests", orders)
        if not workers:
            cycle_state = "read_only_inventory"
        elif errors:
            cycle_state = "worker_failure_retry"
        elif real_progress:
            cycle_state = "new_private_artifacts_verified"
        elif consecutive_stalls >= 3:
            cycle_state = "stalled_requires_source_or_review_recovery"
        else:
            cycle_state = "idle_no_new_artifacts_retry"
        report = {
            "schema": SCHEMA, "updated_utc": datetime.now(timezone.utc).isoformat(),
            "order_count": 200, "planned_bilingual_editions": 400,
            "stage_results": results, "before": before, "after": after,
            "new_artifacts_by_stage": diffs,
            "qc_feedback": qc_rework_facts(area),
            "worker_errors": errors,
            "cycle_state": cycle_state,
            "generated_new_artifacts": real_progress,
            "consecutive_no_progress_ticks": consecutive_stalls,
            "missing_stage2_orders": len(awaiting_sources),
            "missing_stage2_order_ids_sample": awaiting_sources[:20],
            "missing_v003_orders": len(awaiting_revisions),
            "missing_v003_order_ids_sample": awaiting_revisions[:20],
            "needs_independent_approval_before_sale": True,
            "next_cycle_policy": "VPS_LOCAL_EVERY_MINUTE_SKIP_IF_PREVIOUS_ACTIVE",
            "same_revision_retries_do_not_equal_new_products": True,
            "qc1000_approved_by_internal_workers": 0,
            "independent_expert_signatures_fabricated": False,
            "public_products_released_by_loop": 0,
            "public_sites_modified": False,
        }
        if workers:
            save_atomic(state / "autonomous-closed-loop-status.json", report)
        return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--operations", required=True)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    result = run_tick(args.factory_private, args.operations,
                      workers=not args.audit_only)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("AUTONOMOUS_LOOP_ERROR:" + type(exc).__name__ + ":" + str(exc)[:160],
              file=sys.stderr)
        raise SystemExit(1)
