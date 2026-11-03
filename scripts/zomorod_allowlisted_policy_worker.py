#!/usr/bin/env python3
"""Apply one explicitly allowlisted company policy from an authenticated private task.

This runner is deliberately not a general command interpreter. All DB and filesystem
targets are fixed, no task text is executed, and execution is idempotently receipted.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import sqlite3
import stat
import sys
import time

PRIVATE = Path("/home/zomorod2/.private/zomorod-business")
DB = PRIVATE / "command-center.sqlite3"
POLICY_FILE = PRIVATE / "factory-single-product-policy-v1.json"
TITLE = "Enforce the one-product factory production and independent release rule"
DETAIL = (
    "Record the owner's binding operational rule: the VPS factory may process "
    "one non-book product at a time; only after independent QC 1000/1000, a "
    "verified handoff receipt and store acceptance may the next product begin. "
    "Do not enable mass production or disable the existing remote access."
)
EVENT_KIND = "bridge_factory_single_product_policy_applied"
EVENT_NOTE = "Allowlisted single-product policy applied; execution receipt verified separately"
POLICY = {
    "policy_id": "ZMR_FACTORY_SINGLE_PRODUCT_V1",
    "max_concurrent_products": 1,
    "factory_mass_production_allowed": False,
    "next_product_requires_prior_release": True,
    "independent_quality_review_required": True,
    "required_quality_score": 1000,
    "verified_store_handoff_required": True,
    "existing_remote_access_cannot_be_disabled_by_this_policy": True,
}
DATA = (json.dumps(POLICY, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
DIGEST = hashlib.sha256(DATA).hexdigest()


def validate_identity() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("CPANEL_OWNER_REJECTED")
    if PRIVATE.is_symlink() or not PRIVATE.is_dir() or DB.is_symlink() or not DB.is_file():
        raise RuntimeError("PRIVATE_DB_REJECTED")


def connect(*, readonly: bool) -> sqlite3.Connection:
    validate_identity()
    mode = "ro" if readonly else "rw"
    db = sqlite3.connect(DB.as_uri() + "?mode=" + mode, uri=True, timeout=15, isolation_level=None)
    db.execute("PRAGMA busy_timeout=15000")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def read_policy() -> bytes | None:
    try:
        fd = os.open(POLICY_FILE, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as handle:
        meta = os.fstat(handle.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > 8192 or meta.st_mode & 0o077:
            raise RuntimeError("POLICY_FILE_PERMISSIONS_REJECTED")
        return handle.read(8193)


def ensure_policy_written() -> None:
    existing = read_policy()
    if existing is not None:
        if existing != DATA:
            raise RuntimeError("POLICY_CONFLICT_REJECTED")
        return
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(POLICY_FILE, flags, 0o600)
    except FileExistsError:
        if read_policy() != DATA:
            raise RuntimeError("POLICY_CONFLICT_REJECTED")
        return
    with os.fdopen(fd, "wb") as output:
        output.write(DATA)
        output.flush()
        os.fsync(output.fileno())
    if read_policy() != DATA:
        raise RuntimeError("POLICY_WRITE_VERIFY_FAILED")


def apply() -> None:
    db = connect(readonly=False)
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""
            CREATE TABLE IF NOT EXISTS bridge_execution_receipts (
                id TEXT PRIMARY KEY,
                task_id INTEGER NOT NULL REFERENCES tasks(id),
                execution_kind TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                executed_at INTEGER NOT NULL
            )
        """)
        now = int(time.time())
        # The ingress verified the envelope and wrote all four provenance records.
        rows = db.execute("""
            SELECT r.id, r.task_id
            FROM bridge_receipts r
            JOIN tasks t ON t.id = r.task_id
            JOIN task_quality q ON q.task_id = r.task_id
            WHERE r.accepted_at BETWEEN ? AND ?
              AND t.actor_id = 0 AND t.request_key = r.id
              AND t.title = ? AND t.detail = ?
              AND EXISTS (
                  SELECT 1 FROM task_events e
                  WHERE e.task_id = t.id AND e.actor_id = 0
                    AND e.kind = 'bridge_signed_task'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM bridge_execution_receipts x WHERE x.id = r.id
              )
        """, (now - 180, now + 30, TITLE, DETAIL)).fetchall()
        if not rows:
            db.commit()
            print("POLICY_APPLIED=NOT_APPLICABLE")
            return
        if len(rows) != 1:
            raise RuntimeError("AMBIGUOUS_ALLOWLISTED_TASK")
        command_id, task_id = rows[0]
        if not isinstance(command_id, str) or not re.fullmatch(r"[0-9a-f]{32}", command_id):
            raise RuntimeError("COMMAND_ID_REJECTED")
        ensure_policy_written()
        db.execute("""
            INSERT INTO task_events(task_id, actor_id, kind, note)
            VALUES (?, 0, ?, ?)
        """, (task_id, EVENT_KIND, EVENT_NOTE))
        db.execute("""
            INSERT INTO bridge_execution_receipts
                (id, task_id, execution_kind, content_sha256, executed_at)
            VALUES (?, ?, ?, ?, ?)
        """, (command_id, task_id, POLICY["policy_id"], DIGEST, now))
        db.commit()
        print("POLICY_APPLIED=YES")
        print("POLICY_COMMAND_ID=" + command_id)
    except Exception:
        if db.in_transaction:
            db.rollback()
        raise
    finally:
        db.close()


def verify(command_id: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{32}", command_id):
        raise RuntimeError("INVALID_VERIFY_ID")
    if read_policy() != DATA:
        raise RuntimeError("POLICY_READBACK_FAILED")
    db = connect(readonly=True)
    try:
        row = db.execute("""
            SELECT x.task_id
            FROM bridge_execution_receipts x
            JOIN bridge_receipts r ON r.id = x.id AND r.task_id = x.task_id
            JOIN task_events e ON e.task_id = x.task_id AND e.kind = ?
            WHERE x.id = ? AND x.execution_kind = ?
              AND x.content_sha256 = ? AND e.actor_id = 0
        """, (EVENT_KIND, command_id, POLICY["policy_id"], DIGEST)).fetchone()
        if row is None:
            raise RuntimeError("EXECUTION_RECEIPT_READBACK_FAILED")
        print("PRIVATE_POLICY_READBACK=VERIFIED")
        print("PRIVATE_EXECUTION_RECEIPT=VERIFIED")
    finally:
        db.close()


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "apply":
        apply()
    elif len(sys.argv) == 3 and sys.argv[1] == "verify":
        verify(sys.argv[2])
    else:
        raise RuntimeError("ACTION_NOT_ALLOWED")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, sqlite3.Error, RuntimeError):
        print("PRIVATE_POLICY_WORKER=REJECTED", file=sys.stderr)
        sys.exit(2)
