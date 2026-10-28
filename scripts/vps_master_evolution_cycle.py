#!/usr/bin/env python3
"""Bounded VPS master-agent strategy evolution from private, verified task states.

No database writes, network calls, financial actions or self-editing source code.
The private master runner is permanently capped at one step per cycle.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile


def evaluate(db_path: Path, state_path: Path):
    db_path = db_path.expanduser()
    state_path = state_path.expanduser()
    if not db_path.is_file() or db_path.is_symlink():
        raise RuntimeError("MASTER_PRIVATE_DB_NOT_FOUND")
    if state_path.exists() and state_path.is_symlink():
        raise RuntimeError("MASTER_EVOLUTION_STATE_SYMLINK")
    state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(state_path.parent, 0o700)
    with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=12) as db:
        db.execute("PRAGMA query_only=ON")
        row = db.execute("SELECT id FROM core_agent WHERE code=? AND active=1 LIMIT 1",
                         ("economic-master-agent",)).fetchone()
        if not row:
            raise RuntimeError("MASTER_AGENT_NOT_ACTIVE")
        counts = dict(db.execute(
            "SELECT status,COUNT(*) FROM core_agenttask WHERE agent_id=? GROUP BY status",
            (row[0],)).fetchall())
    # A "completed" row is not necessarily a new commercial outcome. Inspect
    # recent signed-off execution results and require action diversity before
    # increasing the master's execution budget. Never read private payloads
    # into public logs or send them to a model.
    with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=12) as db:
        db.execute("PRAGMA query_only=ON")
        rows = db.execute(
            "SELECT action_type,output_data FROM core_agenttask "
            "WHERE agent_id=? AND status='completed' "
            "ORDER BY id DESC LIMIT 128", (row[0],)
        ).fetchall()
    recent_verified_actions = []
    for action, raw in rows:
        try:
            evidence = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if isinstance(evidence, dict) and evidence.get("verified_effect") is True:
            recent_verified_actions.append(str(action))
    allowed = ("completed", "failed", "blocked", "queued", "running")
    counts = {key: int(counts.get(key, 0)) for key in allowed}
    previous = {}
    if state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
        if previous.get("schema") != "saeit.master.evolution.v1":
            raise RuntimeError("UNKNOWN_PREVIOUS_EVOLUTION_STATE")
    prev_count = previous.get("task_counts", {})
    delta_completed = counts["completed"] - int(prev_count.get("completed", counts["completed"]))
    delta_failed = counts["failed"] - int(prev_count.get("failed", counts["failed"]))
    delta_blocked = counts["blocked"] - int(prev_count.get("blocked", counts["blocked"]))
    old_steps = int(previous.get("max_steps", 1))
    if old_steps not in (1, 2, 3):
        raise RuntimeError("INVALID_PREVIOUS_EVOLUTION_POLICY")
    # Compare only the newly completed portion, not historical successes.
    recent_new = recent_verified_actions[:min(max(delta_completed, 0), len(recent_verified_actions))]
    diversity = len(set(recent_new))
    # The owner requested controlled production with no volume expansion.
    # Keep one master task per five-minute cycle even after diverse successes.
    steps = 1
    if old_steps != 1:
        decision = "rollback_to_single_step_volume_cap"
    elif delta_failed > 0 or delta_blocked > 0:
        decision = "hold_single_step_after_regression"
    elif delta_completed >= 2 and diversity >= 2 and counts["blocked"] == 0:
        decision = "hold_single_step_after_verified_progress"
    elif delta_completed >= 2:
        decision = "hold_single_step_no_verified_diversity"
    else:
        decision = "hold_single_step_until_verified_progress"
    report = {
        "schema": "saeit.master.evolution.v1",
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "agent_code": "economic-master-agent",
        "operating_mode": "private_vps_single_step_controlled",
        "task_counts": counts,
        "delta": {"verified_completed_tasks": delta_completed,
                  "failed_tasks": delta_failed, "blocked_tasks": delta_blocked},
        "recent_new_verified_action_types": diversity,
        "repeat_completion_is_not_diverse_progress": True,
        "max_steps": steps,
        "hard_max_steps_cap": 1,
        "volume_scaling_enabled": False,
        "parallel_master_tasks": False,
        "previous_max_steps": old_steps,
        "decision": decision,
        "revision": int(previous.get("revision", 0)) + int(steps != old_steps),
        "self_modifying_code": False,
        "capacity_policy_change": "disabled_by_owner_volume_cap",
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
