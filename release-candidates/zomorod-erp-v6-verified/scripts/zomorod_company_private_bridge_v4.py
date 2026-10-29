#!/usr/bin/env python3
"""Private Zomorod command bridge. CLI-only, no HTTP listener, no scheduler.

Accepts ONLY signed task.create commands. The signing key belongs to private
server storage; never write it, command payloads or task contents to GitHub.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import stat
import sys
import time
from pathlib import Path

HEX32 = re.compile(r"^[0-9a-f]{32}$")
WORKSTREAMS = frozenset(("company", "finance", "sales", "inventory", "personnel",
                         "projects", "research", "operations"))
PRIORITIES = frozenset(("normal", "high", "critical"))
RISKS = frozenset(("read_only", "internal_write", "high_impact"))
ENVELOPE_FIELDS = frozenset(("v", "id", "ts", "op", "task", "sig"))
TASK_FIELDS = frozenset(("workstream", "priority", "risk", "title", "detail",
                         "deliverable", "acceptance"))
MAX_ENVELOPE_BYTES = 8192
MAX_CLOCK_SKEW_SECONDS = 120


class Rejected(Exception):
    pass


def private_path(path: Path, *, must_exist: bool = True) -> Path:
    if not path.is_absolute():
        raise Rejected("not_absolute")
    if path.is_symlink() or path.parent.is_symlink():
        raise Rejected("unsafe_symlink")
    if not path.parent.is_dir():
        raise Rejected("missing_private_dir")
    if path.parent.stat().st_mode & 0o022:
        raise Rejected("unsafe_parent_permissions")
    if must_exist:
        if not path.is_file() or path.is_symlink():
            raise Rejected("missing_file")
        if path.stat().st_mode & 0o077:
            raise Rejected("unsafe_file_permissions")
    return path


def init_key(filename: Path) -> None:
    private_path(filename, must_exist=False)
    if filename.exists() or filename.is_symlink():
        raise Rejected("key_already_exists")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(filename, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(secrets.token_bytes(32))
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        filename.unlink(missing_ok=True)
        raise
    print("PRIVATE_BRIDGE_KEY=CREATED_NOT_DISCLOSED")


def read_key(filename: Path) -> bytes:
    private_path(filename)
    key = filename.read_bytes()
    if len(key) != 32:
        raise Rejected("invalid_private_key")
    return key


def no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise Rejected("duplicate_json_key")
        result[key] = value
    return result


def canonical_body(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def authenticate(envelope: bytes, key: bytes, now: int) -> dict:
    if not 2 <= len(envelope) <= MAX_ENVELOPE_BYTES:
        raise Rejected("invalid_message_size")
    try:
        payload = json.loads(envelope.decode("utf-8"),
                             object_pairs_hook=no_duplicate_keys,
                             parse_constant=lambda _: (_ for _ in ()).throw(Rejected("nonfinite_number")))
    except (ValueError, UnicodeError) as exc:
        raise Rejected("malformed_json") from exc
    if not isinstance(payload, dict) or frozenset(payload) != ENVELOPE_FIELDS:
        raise Rejected("invalid_envelope_fields")
    if type(payload["v"]) is not int or payload["v"] != 1:
        raise Rejected("invalid_protocol_version")
    if not isinstance(payload["id"], str) or not HEX32.fullmatch(payload["id"]):
        raise Rejected("invalid_id")
    if type(payload["ts"]) is not int or abs(now - payload["ts"]) > MAX_CLOCK_SKEW_SECONDS:
        raise Rejected("expired_or_future_command")
    if payload["op"] != "task.create":
        raise Rejected("operation_not_allowed")
    if not isinstance(payload["sig"], str) or not re.fullmatch(r"[0-9a-f]{64}", payload["sig"]):
        raise Rejected("invalid_signature_format")
    body = {k: v for k, v in payload.items() if k != "sig"}
    expected = hmac.new(key, canonical_body(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, payload["sig"]):
        raise Rejected("signature_mismatch")
    task = payload["task"]
    if not isinstance(task, dict) or frozenset(task) != TASK_FIELDS:
        raise Rejected("invalid_task_schema")
    for field in TASK_FIELDS:
        if not isinstance(task[field], str):
            raise Rejected("invalid_task_field")
    for field, allowed in [("workstream", WORKSTREAMS), ("priority", PRIORITIES),
                           ("risk", RISKS)]:
        if task[field] not in allowed:
            raise Rejected("invalid_task_category")
    for field, limit in [("title", 160), ("detail", 2000),
                         ("deliverable", 500), ("acceptance", 1000)]:
        value = task[field].strip()
        if (not value or len(value) > limit or
                any(ord(c) < 32 and c not in "\t\n" for c in value)):
            raise Rejected("invalid_task_text")
    return payload


def open_control_db(path: Path) -> sqlite3.Connection:
    private_path(path)
    uri = path.as_uri() + "?mode=rw"
    connection = sqlite3.connect(uri, uri=True, timeout=15, isolation_level=None)
    connection.execute("PRAGMA busy_timeout=15000")
    connection.execute("PRAGMA foreign_keys=ON")
    expected = ("tasks", "task_events", "task_quality")
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    found = {name for (name,) in rows}
    if not set(expected).issubset(found):
        connection.close()
        raise Rejected("missing_command_center_schema")
    return connection


def import_task(control_db: Path, envelope: bytes, key: bytes, now: int) -> str:
    validated = authenticate(envelope, key, now)
    task = validated["task"]
    db = open_control_db(control_db)
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS bridge_receipts (
            id TEXT PRIMARY KEY,
            task_id INTEGER NOT NULL REFERENCES tasks(id),
            accepted_at INTEGER NOT NULL
        )""")
        existing = db.execute(
            "SELECT task_id FROM bridge_receipts WHERE id=?", (validated["id"],)).fetchone()
        if existing is not None:
            db.commit()
            return "DUPLICATE"
        # Actor=0 is explicitly reserved for an external verified bridge command.
        db.execute("""INSERT INTO tasks(request_key,source_key,workstream,title,
                      detail,priority,actor_id)
                      VALUES(?,?,?,?,?,?,?)""",
                   (validated["id"], None, task["workstream"], task["title"],
                    task["detail"], task["priority"], 0))
        task_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("""INSERT INTO task_quality(task_id,risk,deliverable,acceptance)
                      VALUES(?,?,?,?)""",
                   (task_id, task["risk"], task["deliverable"], task["acceptance"]))
        db.execute("""INSERT INTO task_events(task_id,actor_id,kind,note)
                      VALUES(?,?,?,?)""",
                   (task_id, 0, "bridge_signed_task",
                    "Authenticated private bridge import; not executed"))
        db.execute("INSERT INTO bridge_receipts(id,task_id,accepted_at) VALUES(?,?,?)",
                   (validated["id"], task_id, now))
        db.commit()
        return "ACCEPTED"
    except Exception:
        if db.in_transaction:
            db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Private, allowlisted company command bridge")
    parser.add_argument("action", choices=("init-key", "status", "import-task"))
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "init-key":
            init_key(args.key)
        elif args.action == "status":
            # Never print company tasks, customer records, secret or detailed counts.
            read_key(args.key)
            db = open_control_db(args.db)
            try:
                result = db.execute("PRAGMA quick_check").fetchone()[0]
                if result != "ok":
                    raise Rejected("control_db_integrity")
            finally:
                db.close()
            print("PRIVATE_BRIDGE=READY_SIGNER_NOT_CONNECTED")
            print("AUTONOMOUS_OPERATIONS=DISABLED")
        else:
            key = read_key(args.key)
            raw = sys.stdin.buffer.read(MAX_ENVELOPE_BYTES + 1)
            outcome = import_task(args.db, raw, key, int(time.time()))
            print("SIGNED_COMMAND=" + outcome)
            print("EXTERNAL_EXECUTION=NONE")
        return 0
    except (Rejected, sqlite3.Error, OSError) as exc:
        # Avoid printing any private payload or exception string.
        print("PRIVATE_BRIDGE=REJECTED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
