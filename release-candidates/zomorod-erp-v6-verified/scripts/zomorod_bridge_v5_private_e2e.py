#!/usr/bin/env python3
"""Isolated cPanel CLI bridge end-to-end regression.

This script deliberately uses a throwaway key and database inside an isolated
0700 directory. It NEVER imports into a real company's task or accounting DB.
No real task content or key is written to GitHub, logs, or public_html.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time


class SmokeFailure(Exception):
    pass


def assert_ok(condition: bool, code: str) -> None:
    if not condition:
        raise SmokeFailure(code)


def invoke(script: Path, action: str, db_path: Path, key_path: Path,
           payload: bytes | None = None) -> subprocess.CompletedProcess:
    command = [sys.executable, str(script), action,
               "--db", str(db_path), "--key", str(key_path)]
    return subprocess.run(command, input=payload, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False, timeout=12)


def create_synthetic_schema(path: Path) -> None:
    # Schema is intentionally a minimal compatible synthetic copy.
    with sqlite3.connect(path) as db:
        db.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                request_key TEXT NOT NULL UNIQUE,
                source_key TEXT UNIQUE,
                workstream TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'queued',
                actor_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                closing_note TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE task_quality (
                task_id INTEGER PRIMARY KEY REFERENCES tasks(id),
                risk TEXT NOT NULL,
                deliverable TEXT NOT NULL,
                acceptance TEXT NOT NULL,
                review_state TEXT NOT NULL DEFAULT 'planned',
                evidence_url TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE task_events (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL REFERENCES tasks(id),
                actor_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
    os.chmod(path, 0o600)


def signed_payload(key: bytes, timestamp: int, op: str = "task.create") -> bytes:
    obj = {
        "v": 1,
        "id": "cafecafe123456789abcdeffedcba001",
        "ts": timestamp,
        "op": op,
        "task": {
            "workstream": "operations",
            "priority": "normal",
            "risk": "read_only",
            "title": "Synthetic bridge smoke test",
            "detail": "Temporary data only, no actual company action",
            "deliverable": "Synthetic receipt",
            "acceptance": "Accepted once and rejected on replay/tamper",
        },
    }
    body = json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")
    obj["sig"] = hmac.new(key, body, hashlib.sha256).hexdigest()
    return json.dumps(obj, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def verify_isolated_result(db_path: Path) -> None:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as db:
        tasks = db.execute("SELECT actor_id,state,title FROM tasks").fetchall()
        assert_ok(tasks == [(0, "queued", "Synthetic bridge smoke test")],
                  "expected_one_synthetic_task")
        plans = db.execute(
            "SELECT risk,review_state FROM task_quality").fetchall()
        assert_ok(plans == [("read_only", "planned")], "missing_review_gate")
        events = db.execute("SELECT kind FROM task_events").fetchall()
        assert_ok(events == [("bridge_signed_task",)], "missing_audit_event")
        receipts = db.execute("SELECT COUNT(*) FROM bridge_receipts").fetchone()[0]
        assert_ok(receipts == 1, "duplicate_receipt")


def run(bridge_script: Path, private_dir: Path) -> None:
    assert_ok(bridge_script.is_file() and not bridge_script.is_symlink(),
              "bridge_script_missing")
    assert_ok(private_dir.is_dir() and not private_dir.is_symlink(),
              "unsafe_private_dir")
    # Isolated tests can run on a CI runner or on cPanel. Never use a real DB.
    old_umask = os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory(prefix=".bridge-e2e-only-", dir=private_dir) as temp:
            folder = Path(temp)
            db_path = folder / "synthetic-command.sqlite3"
            key_path = folder / ".synthetic-key"
            create_synthetic_schema(db_path)
            init = invoke(bridge_script, "init-key", db_path, key_path)
            assert_ok(init.returncode == 0 and key_path.is_file(), "key_initialization")
            assert_ok((key_path.stat().st_mode & 0o777) == 0o600, "key_permission")
            key = key_path.read_bytes()
            assert_ok(len(key) == 32, "wrong_key_size")
            ready = invoke(bridge_script, "status", db_path, key_path)
            assert_ok(ready.returncode == 0 and
                      b"READY_SIGNER_NOT_CONNECTED" in ready.stdout, "private_health")
            timestamp = int(time.time())
            valid = signed_payload(key, timestamp)
            accepted = invoke(bridge_script, "import-task", db_path, key_path, valid)
            assert_ok(accepted.returncode == 0 and
                      b"SIGNED_COMMAND=ACCEPTED" in accepted.stdout, "signed_import")
            replay = invoke(bridge_script, "import-task", db_path, key_path, valid)
            assert_ok(replay.returncode == 0 and
                      b"SIGNED_COMMAND=DUPLICATE" in replay.stdout, "replay_dedupe")
            changed = json.loads(valid)
            changed["task"]["title"] = "Modified without re-signing"
            tampered = json.dumps(changed).encode("utf-8")
            rejected = invoke(bridge_script, "import-task", db_path, key_path, tampered)
            assert_ok(rejected.returncode != 0 and
                      b"SIGNED_COMMAND=ACCEPTED" not in rejected.stdout, "tamper_rejected")
            expired = invoke(bridge_script, "import-task", db_path, key_path,
                             signed_payload(key, timestamp - 180))
            assert_ok(expired.returncode != 0, "expired_rejected")
            forbidden = invoke(bridge_script, "import-task", db_path, key_path,
                               signed_payload(key, timestamp, "payment.transfer"))
            assert_ok(forbidden.returncode != 0, "privileged_operation_rejected")
            verify_isolated_result(db_path)
            print("BRIDGE_SYNTHETIC_E2E=PASS")
            print("KEY_AND_DATA=EPHEMERAL_PRIVATE_ONLY")
            print("SIGNED_RECEIPT=PASS DUPLICATE_REJECTED=PASS")
            print("TAMPER_EXPIRY_PRIVILEGED_OP_REJECTED=PASS")
            print("COMPANY_TASK_DB=NOT_USED COMPANY_ACCOUNTING_DB=NOT_USED")
            print("EXTERNAL_CHAT_SIGNER=NOT_CONNECTED")
    finally:
        os.umask(old_umask)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise SmokeFailure("args")
        run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
    except (SmokeFailure, OSError, sqlite3.Error, subprocess.SubprocessError):
        # Keep failures meaningful without printing confidential paths or inputs.
        print("BRIDGE_SYNTHETIC_E2E=FAILED", file=sys.stderr)
        sys.exit(1)
