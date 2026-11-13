#!/usr/bin/env python3
"""Bounded VPS master-agent strategy evolution from private, verified task states.

No database writes, network calls, financial actions or self-editing source code.
The private master runner executes up to 20 serial tasks per cycle, with
single-product, no-spend, and approval guards unchanged.
"""
import argparse
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
from contextlib import closing


MAX_STATE_BYTES = 200_000
MAX_NEW_TASKS_PER_AUDIT = 128
MAX_TRACKED_PENDING_TASKS = 4096
MAX_COMPLETED_GUARD_TASKS = 128
COMPLETED_GUARD_ID = re.compile(r"[1-9][0-9]{0,18}\\Z")
COMPLETED_GUARD_HASH = re.compile(r"[a-f0-9]{64}\\Z")


def _completed_fingerprint(action, raw_output, execution_id, attempt_count):
    """Detect post-completion row mutation across bounded private snapshots.

    This is a local consistency fingerprint, NOT a signed provenance record.
    """
    record = [action, raw_output, execution_id, attempt_count]
    return hashlib.sha256(json.dumps(
        record, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


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
    # Load the previous watermark before opening the database snapshot so
    # late-completing older tasks can be checked in that same snapshot.
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
    prior_guard = previous.get("completed_guard", {})
    if (
        not isinstance(prior_guard, dict)
        or len(prior_guard) > MAX_COMPLETED_GUARD_TASKS
        or any(
            not isinstance(key, str)
            or COMPLETED_GUARD_ID.fullmatch(key) is None
            or type(digest) is not str
            or COMPLETED_GUARD_HASH.fullmatch(digest) is None
            for key, digest in prior_guard.items()
        )
    ):
        raise RuntimeError("MASTER_EVOLUTION_COMPLETED_GUARD_INVALID")
    if prior_guard and type(previous.get("last_completed_task_id")) is not int:
        raise RuntimeError("MASTER_EVOLUTION_COMPLETED_GUARD_CURSOR_MISSING")
    if prior_guard and any(
        int(key) > previous["last_completed_task_id"] for key in prior_guard
    ):
        raise RuntimeError("MASTER_EVOLUTION_COMPLETED_GUARD_AHEAD_OF_CURSOR")
    prior_pending = previous.get("pending_prior_ids")
    if prior_pending is not None:
        if (not isinstance(prior_pending, list)
                or len(prior_pending) > MAX_TRACKED_PENDING_TASKS
                or any(type(item) is not int or item <= 0 for item in prior_pending)
                or prior_pending != sorted(set(prior_pending))
                or type(previous.get("last_completed_task_id")) is not int):
            raise RuntimeError("MASTER_EVOLUTION_PENDING_IDS_INVALID")

    # Keep counts, completed tasks and pending-task transitions on one
    # consistent read-only SQLite snapshot (no production DB mutations).
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
            "SELECT id,action_type,output_data,execution_id,attempt_count "
            "FROM core_agenttask WHERE agent_id=? AND status='completed' "
            "ORDER BY id DESC LIMIT ?", (row[0], MAX_NEW_TASKS_PER_AUDIT + 1)
        ).fetchall()
        latest_completed_id = db.execute(
            "SELECT COALESCE(MAX(id),0) FROM core_agenttask "
            "WHERE agent_id=? AND status='completed'", (row[0],)
        ).fetchone()[0]
        # A previously completed high-watermark task can be reopened. Keep
        # that cursor monotone if its row still exists, without re-crediting it.
        prior_cursor_value = previous.get("last_completed_task_id")
        cursor_row = (
            db.execute(
                "SELECT status FROM core_agenttask WHERE agent_id=? AND id=?",
                (row[0], prior_cursor_value),
            ).fetchone()
            if type(prior_cursor_value) is int and prior_cursor_value > 0
            else None
        )
        # Never lose already-tracked unfinished tasks merely because the
        # most recently completed high-watermark task was reopened.
        tracking_ceiling = max(
            latest_completed_id,
            prior_cursor_value
            if type(prior_cursor_value) is int and prior_cursor_value >= 0 else 0,
        )
        pending_ids = [
            item[0] for item in db.execute(
                "SELECT id FROM core_agenttask WHERE agent_id=? "
                "AND status!='completed' AND id<=? ORDER BY id LIMIT ?",
                (row[0], tracking_ceiling, MAX_TRACKED_PENDING_TASKS + 1)
            ).fetchall()
        ]
        if len(pending_ids) > MAX_TRACKED_PENDING_TASKS:
            raise RuntimeError("MASTER_EVOLUTION_PENDING_TRACKING_LIMIT_EXCEEDED")
        prior_pending_rows = []
        for offset in range(0, len(prior_pending or []), 128):
            batch = prior_pending[offset:offset + 128]
            placeholders = ",".join("?" for _ in batch)
            prior_pending_rows.extend(db.execute(
                "SELECT id,status,action_type,output_data FROM core_agenttask "
                "WHERE agent_id=? AND id IN (" + placeholders + ")",
                (row[0], *batch)
            ).fetchall())
        if len(prior_pending_rows) != len(prior_pending or []):
            raise RuntimeError("MASTER_EVOLUTION_PREVIOUS_PENDING_TASK_DISAPPEARED")
        guard_rows = []
        guard_ids = [int(key) for key in prior_guard]
        for offset in range(0, len(guard_ids), 128):
            batch = guard_ids[offset:offset + 128]
            placeholders = ",".join("?" for _ in batch)
            guard_rows.extend(db.execute(
                "SELECT id,status,action_type,output_data,execution_id,attempt_count "
                "FROM core_agenttask WHERE agent_id=? AND id IN ("
                + placeholders + ")", (row[0], *batch)
            ).fetchall())
        if len(guard_rows) != len(guard_ids):
            raise RuntimeError("MASTER_EVOLUTION_COMPLETED_GUARD_TASK_MISSING")
    guarded_reopened_ids = []
    for task_id, status, action, raw, execution_id, attempt_count in guard_rows:
        if status != "completed":
            guarded_reopened_ids.append(task_id)
        elif _completed_fingerprint(
                action, raw, execution_id, attempt_count
        ) != prior_guard[str(task_id)]:
            raise RuntimeError("MASTER_EVOLUTION_COMPLETED_EVIDENCE_CHANGED")
    allowed = ("completed", "failed", "blocked", "queued", "running")
    counts = {key: int(counts.get(key, 0)) for key in allowed}
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
    watermark_reopened = False
    previous_cursor = previous.get("last_completed_task_id")
    if previous_cursor is not None:
        if type(previous_cursor) is not int or previous_cursor < 0:
            raise RuntimeError("INVALID_PREVIOUS_EVOLUTION_TASK_CURSOR")
        if previous_cursor > 0 and cursor_row is None:
            raise RuntimeError("MASTER_EVOLUTION_TASK_CURSOR_AHEAD_OF_DATABASE")
        # Independently inspect the old high-watermark row. New higher-ID
        # completions can otherwise mask its reopening in the total counts.
        watermark_reopened = (
            previous_cursor > 0 and cursor_row[0] != "completed"
        )
        if previous_cursor > latest_completed_id and not watermark_reopened:
            raise RuntimeError("MASTER_EVOLUTION_TASK_CURSOR_AHEAD_OF_DATABASE")
        cursor_trusted = True
    elif previous and prev_count.get("completed") == 0:
        previous_cursor = 0
        cursor_trusted = True
    else:
        previous_cursor = latest_completed_id
        cursor_trusted = False
    # Querying one extra row makes the audit-window limit exact, even when
    # task IDs are contiguous; the old gap-based detection missed that case.
    if sum(task_id > previous_cursor for task_id, *_ in rows) > MAX_NEW_TASKS_PER_AUDIT:
        raise RuntimeError("MASTER_EVOLUTION_NEW_TASKS_EXCEED_AUDIT_WINDOW")
    if prior_pending is not None and any(item > previous_cursor for item in prior_pending):
        raise RuntimeError("MASTER_EVOLUTION_PENDING_IDS_EXCEED_CURSOR")
    # Only pending tasks first seen ABOVE the previous high-watermark or
    # already tracked as pending are eligible to be credited later. An old
    # completed task that is reset to queued is otherwise indistinguishable
    # from a genuinely unfinished old task and could be double counted.
    previously_tracked = set(prior_pending or ())
    eligible_pending_ids = [
        task_id for task_id in pending_ids
        if task_id > previous_cursor or task_id in previously_tracked
    ]
    suppressed_reopened_or_unproven = len(pending_ids) - len(eligible_pending_ids)
    recent_new = []
    for task_id, action, raw, execution_id, attempt_count in rows:
        if task_id <= previous_cursor:
            continue
        try:
            evidence = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if isinstance(evidence, dict) and evidence.get("verified_effect") is True:
            recent_new.append(str(action))
    # A task can finish AFTER a newer-ID task. Only count those older IDs if
    # they were recorded as unfinished during the previous verified snapshot.
    late_completed = 0
    late_verified = 0
    for task_id, status, action, raw in prior_pending_rows:
        if status != "completed":
            continue
        late_completed += 1
        try:
            evidence = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if isinstance(evidence, dict) and evidence.get("verified_effect") is True:
            recent_new.append(str(action))
            late_verified += 1
    diversity = len(set(recent_new))
    # Serial task depth is distinct from factory product volume. Never run
    # parallel master tasks or remove financial/owner approval gates.
    regressed = (delta_failed > 0 or delta_blocked > 0
                 or counts["blocked"] > 0 or delta_completed < 0
                 or watermark_reopened or bool(guarded_reopened_ids))
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
    # The most recent 128 completed tasks become the next-cycle integrity
    # baseline; older history remains unproven, not cryptographically signed.
    new_guard = {
        str(task_id): _completed_fingerprint(
            action, raw, execution_id, attempt_count
        )
        for task_id, action, raw, execution_id, attempt_count
        in rows[:MAX_COMPLETED_GUARD_TASKS]
    }
    report = {
        "schema": "saeit.master.evolution.v1",
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "agent_code": "economic-master-agent",
        "operating_mode": "private_vps_serial_tasks_controlled",
        "task_counts": counts,
        "delta": {"verified_completed_tasks": len(recent_new),
                  "completed_tasks_net_change": delta_completed,
                  "failed_tasks": delta_failed, "blocked_tasks": delta_blocked},
        "last_completed_task_id": max(previous_cursor, latest_completed_id),
        "completed_guard": new_guard,
        "completed_guard_scope": "bounded_recent_task_consistency_not_signed_attestation",
        "previous_completed_guard_available": "completed_guard" in previous,
        "previous_completed_guard_rows_checked": len(guard_rows),
        "guarded_reopened_task_count": len(guarded_reopened_ids),
        "pending_prior_ids": eligible_pending_ids,
        "suppressed_unproven_prior_pending_count": suppressed_reopened_or_unproven,
        "watermark_task_reopened": watermark_reopened,
        "previous_pending_tracking_available": prior_pending is not None,
        "late_completed_tasks": late_completed,
        "late_verified_completed_tasks": late_verified,
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
