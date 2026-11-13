#!/usr/bin/env python3
"""Bounded VPS master-agent strategy evolution from private, verified task states.

No database writes, network calls, financial actions or self-editing source code.
The private master runner executes up to 20 serial tasks per cycle, with
single-product, no-spend, and approval guards unchanged.
"""
import argparse
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
from contextlib import closing


MAX_STATE_BYTES = 200_000
MAX_NEW_TASKS_PER_AUDIT = 128


def _contains_symlink(path):
    return any(part.is_symlink() for part in (path, *path.parents))


def evaluate(db_path: Path, state_path: Path):
    db_path = db_path.expanduser()
    state_path = state_path.expanduser()
    if _contains_symlink(db_path) or not db_path.is_file():
        raise RuntimeError("MASTER_PRIVATE_DB_NOT_FOUND")
    if state_path.is_symlink():
        raise RuntimeError("MASTER_EVOLUTION_STATE_SYMLINK")
    # Never chmod an existing shared directory: a failed policy check must not
    # change permissions of unrelated private or operational files.
    parent = state_path.parent
    if _contains_symlink(parent):
        raise RuntimeError("MASTER_EVOLUTION_STATE_PARENT_SYMLINK")
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent_mode = parent.stat().st_mode
    if not stat.S_ISDIR(parent_mode) or stat.S_IMODE(parent_mode) & 0o077:
        raise RuntimeError("MASTER_EVOLUTION_STATE_DIR_NOT_PRIVATE")
    # Keep counts and completed-task IDs on one consistent read-only SQLite
    # snapshot. Separate connections can see different concurrent task states.
    with closing(sqlite3.connect(
            db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=12
    )) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        row = db.execute(
            "SELECT id FROM core_agent WHERE code=? AND active=1 LIMIT 1",
            ("economic-master-agent",)
        ).fetchone()
        if not row:
            raise RuntimeError("MASTER_AGENT_NOT_ACTIVE")
        counts = dict(db.execute(
            "SELECT status,COUNT(*) FROM core_agenttask "
            "WHERE agent_id=? GROUP BY status", (row[0],)
        ).fetchall())
        rows = db.execute(
            "SELECT id,action_type,output_data FROM core_agenttask "
            "WHERE agent_id=? AND status='completed' "
            "ORDER BY id DESC LIMIT ?", (row[0], MAX_NEW_TASKS_PER_AUDIT)
        ).fetchall()
        latest_completed_id = db.execute(
            "SELECT COALESCE(MAX(id),0) FROM core_agenttask "
            "WHERE agent_id=? AND status='completed'", (row[0],)
        ).fetchone()[0]
    allowed = ("completed", "failed", "blocked", "queued", "running")
    counts = {key: int(counts.get(key, 0)) for key in allowed}
    previous = {}
    if state_path.exists():
        if not state_path.is_file() or state_path.stat().st_size > MAX_STATE_BYTES:
            raise RuntimeError("MASTER_EVOLUTION_STATE_UNSAFE")
        try:
            previous = json.loads(state_path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError("MASTER_EVOLUTION_STATE_INVALID_JSON") from exc
        if not isinstance(previous, dict) or previous.get("schema") != "saeit.master.evolution.v1":
            raise RuntimeError("UNKNOWN_PREVIOUS_EVOLUTION_STATE")
    prev_count = previous.get("task_counts", {})
    if not isinstance(prev_count, dict) or any(
            type(prev_count.get(key, counts[key])) is not int
            or prev_count.get(key, counts[key]) < 0
            for key in allowed
    ):
        raise RuntimeError("MASTER_EVOLUTION_PREVIOUS_COUNTS_INVALID")
    delta_completed = counts["completed"] - prev_count.get("completed", counts["completed"])
    delta_failed = counts["failed"] - prev_count.get("failed", counts["failed"])
    delta_blocked = counts["blocked"] - prev_count.get("blocked", counts["blocked"])
    old_steps = previous.get("max_steps", 1)
    if type(old_steps) is not int or old_steps not in (1, 2, 3, 20):
        raise RuntimeError("INVALID_PREVIOUS_EVOLUTION_POLICY")
    # A count delta cannot identify which completed tasks are newly verified.
    # Persist a stable task-ID watermark. Legacy states without a cursor can
    # credit events only when the previous completed count was genuinely zero;
    # otherwise abstain from claiming any historical actions as new progress.
    previous_cursor = previous.get("last_completed_task_id")
    if previous_cursor is not None:
        if type(previous_cursor) is not int or previous_cursor < 0:
            raise RuntimeError("INVALID_PREVIOUS_EVOLUTION_TASK_CURSOR")
        if previous_cursor > latest_completed_id:
            raise RuntimeError("MASTER_EVOLUTION_TASK_CURSOR_AHEAD_OF_DATABASE")
        cursor_trusted = True
    elif previous and prev_count.get("completed") == 0:
        previous_cursor = 0
        cursor_trusted = True
    else:
        previous_cursor = latest_completed_id
        cursor_trusted = False
    if previous_cursor < latest_completed_id:
        newest_ids = [task_id for task_id, _, _ in rows]
        if len(newest_ids) == MAX_NEW_TASKS_PER_AUDIT and min(newest_ids) > previous_cursor + 1:
            # Count records, not contiguous IDs: task IDs may contain gaps.
            with closing(sqlite3.connect(
                    db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=12
            )) as db:
                db.execute("PRAGMA query_only=ON")
                new_total = db.execute(
                    "SELECT COUNT(*) FROM core_agenttask WHERE agent_id=? "
                    "AND status='completed' AND id>?",
                    (row[0], previous_cursor)
                ).fetchone()[0]
            if new_total > len(rows):
                raise RuntimeError("MASTER_EVOLUTION_NEW_TASKS_EXCEED_AUDIT_WINDOW")
    recent_new = []
    for task_id, action, raw in rows:
        if task_id <= previous_cursor:
            continue
        try:
            evidence = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if isinstance(evidence, dict) and evidence.get("verified_effect") is True:
            recent_new.append(str(action))
    diversity = len(set(recent_new))
    # Serial task depth is distinct from factory product volume. Never run
    # parallel master tasks or remove financial/owner approval gates.
    regressed = delta_failed > 0 or delta_blocked > 0 or counts["blocked"] > 0
    steps = 1 if regressed else 20
    if regressed:
        decision = "limit_serial_steps_after_regression"
    elif old_steps != 20:
        decision = "enable_serial_chain_up_to_20"
    elif len(recent_new) >= 2 and diversity >= 2:
        decision = "hold_serial_chain_after_verified_progress"
    elif len(recent_new) >= 2:
        decision = "hold_serial_chain_no_verified_diversity"
    else:
        decision = "hold_serial_chain_until_verified_progress"
    if type(previous.get("revision", 0)) is not int or previous.get("revision", 0) < 0:
        raise RuntimeError("MASTER_EVOLUTION_PREVIOUS_REVISION_INVALID")
    report = {
        "schema": "saeit.master.evolution.v1",
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "agent_code": "economic-master-agent",
        "operating_mode": "private_vps_serial_tasks_controlled",
        "task_counts": counts,
        "delta": {"verified_completed_tasks": len(recent_new),
                  "completed_tasks_net_change": delta_completed,
                  "failed_tasks": delta_failed, "blocked_tasks": delta_blocked},
        "last_completed_task_id": latest_completed_id,
        "previous_completed_cursor_trusted": cursor_trusted,
        "recent_new_verified_action_types": diversity,
        "repeat_completion_is_not_diverse_progress": True,
        "max_steps": steps,
        "hard_max_steps_cap": 20,
        "volume_scaling_enabled": False,
        "parallel_master_tasks": False,
        "previous_max_steps": old_steps,
        "decision": decision,
        "revision": previous.get("revision", 0) + int(steps != old_steps),
        "self_modifying_code": False,
        "capacity_policy_change": "serial_task_depth_only_no_product_volume_expansion",
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
