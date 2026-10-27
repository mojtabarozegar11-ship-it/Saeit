#!/usr/bin/env python3
"""Bounded VPS master-agent strategy evolution from private, verified task states.

No database writes, network calls, financial actions or self-editing source code.
Only the private master runner's max-steps parameter may change (1..3).
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile


def _read_completion_watermark(previous):
    """Return previously observed task identities, or None for safe bootstrap."""
    mark = previous.get("completion_watermark")
    if mark is None:
        return None  # v1 state migration: never infer new work from old counts
    if not isinstance(mark, dict):
        raise RuntimeError("INVALID_COMPLETION_WATERMARK")
    last = mark.get("max_task_id")
    pending = mark.get("incomplete_task_ids")
    complete = mark.get("complete")
    if (type(last) is not int or last < 0 or not isinstance(pending, list)
            or type(complete) is not bool or len(pending) > 50000
            or any(type(item) is not int or item < 1 or item > last for item in pending)
            or len(set(pending)) != len(pending)):
        raise RuntimeError("INVALID_COMPLETION_WATERMARK")
    return (last, set(pending)) if complete else None


def evaluate(db_path: Path, state_path: Path):
    db_path = db_path.expanduser()
    state_path = state_path.expanduser()
    if not db_path.is_file() or db_path.is_symlink():
        raise RuntimeError("MASTER_PRIVATE_DB_NOT_FOUND")
    if state_path.exists() and state_path.is_symlink():
        raise RuntimeError("MASTER_EVOLUTION_STATE_SYMLINK")
    state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(state_path.parent, 0o700)

    previous = {}
    if state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(previous, dict) or previous.get("schema") != "saeit.master.evolution.v1":
            raise RuntimeError("UNKNOWN_PREVIOUS_EVOLUTION_STATE")
    prior_watermark = _read_completion_watermark(previous)
    old_steps = int(previous.get("max_steps", 1))
    if old_steps not in (1, 2, 3):
        raise RuntimeError("INVALID_PREVIOUS_EVOLUTION_POLICY")

    # All observations, including evidence reads, share one SQLite snapshot.
    # No private output_data is exported in logs or the state report.
    with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=12) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        row = db.execute(
            "SELECT id FROM core_agent WHERE code=? AND active=1 LIMIT 1",
            ("economic-master-agent",)
        ).fetchone()
        if not row:
            raise RuntimeError("MASTER_AGENT_NOT_ACTIVE")
        agent_id = row[0]
        task_statuses = db.execute(
            "SELECT id,status FROM core_agenttask WHERE agent_id=? ORDER BY id",
            (agent_id,)
        ).fetchall()
        allowed = ("completed", "failed", "blocked", "queued", "running")
        counts = {key: 0 for key in allowed}
        incomplete_ids = []
        max_task_id = 0
        new_completed_ids = []
        for task_id, status in task_statuses:
            max_task_id = max(max_task_id, task_id)
            if status in counts:
                counts[status] += 1
            if status != "completed":
                incomplete_ids.append(task_id)
            elif (prior_watermark is not None
                  and (task_id > prior_watermark[0] or task_id in prior_watermark[1])):
                new_completed_ids.append(task_id)

        # If the database was reset or IDs regressed, identities are no longer
        # comparable. Never increase capacity on this snapshot.
        identity_continuity = (prior_watermark is not None
                               and max_task_id >= prior_watermark[0])
        if not identity_continuity:
            new_completed_ids = []

        verified_actions = []
        for offset in range(0, len(new_completed_ids), 400):
            chunk = new_completed_ids[offset:offset + 400]
            placeholders = ",".join("?" for _ in chunk)
            rows = db.execute(
                "SELECT action_type,output_data FROM core_agenttask "
                "WHERE agent_id=? AND status='completed' AND id IN (" + placeholders + ")",
                (agent_id, *chunk)
            ).fetchall()
            for action, raw in rows:
                try:
                    evidence = json.loads(raw) if isinstance(raw, str) else raw
                except (TypeError, ValueError):
                    continue
                if (isinstance(evidence, dict)
                        and evidence.get("verified_effect") is True
                        and isinstance(action, str) and action.strip()):
                    verified_actions.append(action.strip())

    prev_count = previous.get("task_counts", {})
    delta_completed = counts["completed"] - int(prev_count.get("completed", counts["completed"]))
    delta_failed = counts["failed"] - int(prev_count.get("failed", counts["failed"]))
    delta_blocked = counts["blocked"] - int(prev_count.get("blocked", counts["blocked"]))
    diversity = len(set(verified_actions))
    watermark_complete = len(incomplete_ids) <= 50000
    if delta_failed > 0 or delta_blocked > 0:
        steps, decision = 1, "rollback_to_conservative_after_regression"
    elif delta_completed < 0 or (identity_continuity and delta_completed < len(new_completed_ids)):
        steps, decision = 1, "rollback_after_task_history_regression"
    elif not identity_continuity or not watermark_complete:
        steps, decision = old_steps, "hold_until_completion_identity_baselined"
    elif len(new_completed_ids) >= 2 and diversity < 2:
        steps, decision = 1, "rollback_repeated_or_unverified_completions"
    elif len(new_completed_ids) >= 2 and diversity >= 2 and counts["blocked"] == 0:
        steps, decision = min(3, old_steps + 1), "diverse_verified_actions_expand_bounded_cycle"
    else:
        steps, decision = old_steps, "hold_strategy_until_measurable_progress"
    report = {
        "schema": "saeit.master.evolution.v1",
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "agent_code": "economic-master-agent",
        "operating_mode": "private_vps_benchmark_adaptive",
        "task_counts": counts,
        "delta": {"completed_tasks": delta_completed,
                  "verified_completed_tasks": len(verified_actions),
                  "failed_tasks": delta_failed, "blocked_tasks": delta_blocked},
        "newly_completed_task_count": len(new_completed_ids),
        "newly_verified_task_count": len(verified_actions),
        "recent_new_verified_action_types": diversity,
        "completion_identity_continuity": identity_continuity,
        "completion_watermark": {
            "max_task_id": max_task_id,
            "incomplete_task_ids": incomplete_ids if watermark_complete else [],
            "complete": watermark_complete,
        },
        "repeat_completion_is_not_diverse_progress": True,
        "max_steps": steps,
        "previous_max_steps": old_steps,
        "decision": decision,
        "revision": int(previous.get("revision", 0)) + int(steps != old_steps),
        "self_modifying_code": False,
        "reversible_parameter_adaptation": True,
        "commercial_publication_enabled": False,
        "financial_actions_enabled": False,
    }
    handle, temp = tempfile.mkstemp(prefix=".evolution-", dir=str(state_path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            json.dump(report, output, indent=2, ensure_ascii=False, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, state_path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    print("MASTER_EVOLUTION_EVALUATED")
    print("MASTER_EVOLUTION_MAX_STEPS=" + str(steps))
    print("MASTER_EVOLUTION_DECISION=" + decision)
    print("MASTER_EVOLUTION_REVISION=" + str(report["revision"]))
    print("MASTER_EVOLUTION_CODE_SELF_EDITING=false")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    args = parser.parse_args()
    evaluate(args.db, args.state)
