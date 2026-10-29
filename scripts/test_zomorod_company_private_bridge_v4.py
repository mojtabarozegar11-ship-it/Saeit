#!/usr/bin/env python3
"""Synthetic isolation and security regression suite for private bridge v4."""
import hashlib
import hmac
import importlib.util
import json
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("zomorod_company_private_bridge_v4.py")
spec = importlib.util.spec_from_file_location("company_bridge", SCRIPT)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zm-bridge-synthetic-")
        self.root = Path(self.temp.name)
        self.dbfile = self.root / "command-center.sqlite3"
        self.keyfile = self.root / ".private-bridge.key"
        bridge.init_key(self.keyfile)
        self.assertEqual(self.keyfile.stat().st_mode & 0o777, 0o600)
        self.key = bridge.read_key(self.keyfile)
        self.now = int(time.time())
        with sqlite3.connect(self.dbfile) as db:
            db.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY,
                    request_key TEXT NOT NULL UNIQUE,
                    source_key TEXT UNIQUE,
                    workstream TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL,
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
                    note TEXT NOT NULL,
                    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)
        os.chmod(self.dbfile, 0o600)
        self.task = {
            "workstream": "projects",
            "priority": "high",
            "risk": "read_only",
            "title": "گزارش پژوهشی <script>alert(1)</script>",
            "detail": "بررسی دستی شواهد بدون اجرای خارجی",
            "deliverable": "گزارش پژوهشی قابل بررسی",
            "acceptance": "ارجاع مستند و آزمون مستقل",
        }

    def tearDown(self):
        self.temp.cleanup()

    def envelope(self, **overrides):
        body = dict(v=1, id="a" * 32, ts=self.now, op="task.create", task=self.task.copy())
        body.update(overrides)
        body["sig"] = hmac.new(self.key, bridge.canonical_body(body),
                               hashlib.sha256).hexdigest()
        return json.dumps(body, ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8")

    def counts(self):
        with sqlite3.connect(self.dbfile) as db:
            return (db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
                    db.execute("SELECT COUNT(*) FROM task_quality").fetchone()[0],
                    db.execute("SELECT COUNT(*) FROM task_events").fetchone()[0])

    def test_signature_and_atomic_idempotent_create(self):
        raw = self.envelope()
        self.assertEqual(bridge.import_task(self.dbfile, raw, self.key, self.now), "ACCEPTED")
        self.assertEqual(self.counts(), (1, 1, 1))
        self.assertEqual(bridge.import_task(self.dbfile, raw, self.key, self.now), "DUPLICATE")
        self.assertEqual(self.counts(), (1, 1, 1))
        with sqlite3.connect(self.dbfile) as db:
            row = db.execute("SELECT actor_id,title,priority,state FROM tasks").fetchone()
            self.assertEqual(row, (0, self.task["title"], "high", "queued"))
            self.assertEqual(db.execute("SELECT review_state FROM task_quality").fetchone()[0],
                             "planned")
            self.assertEqual(db.execute("SELECT kind FROM task_events").fetchone()[0],
                             "bridge_signed_task")

    def test_authentication_blocks_modified_payload_and_fake_signatures(self):
        raw = json.loads(self.envelope().decode("utf-8"))
        raw["task"]["title"] = "forged change"
        with self.assertRaises(bridge.Rejected):
            bridge.import_task(self.dbfile, json.dumps(raw).encode(), self.key, self.now)
        self.assertEqual(self.counts(), (0, 0, 0))
        with self.assertRaises(bridge.Rejected):
            bridge.import_task(self.dbfile, self.envelope(sig="0" * 64), self.key, self.now)

    def test_old_future_replayed_and_wrong_operation_rejected(self):
        for changed in (
            {"ts": self.now - 121},
            {"ts": self.now + 121},
            {"op": "payment.transfer"},
            {"op": "task.finish"},
            {"v": 2},
            {"id": "../private"},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(bridge.Rejected):
                    bridge.import_task(self.dbfile, self.envelope(**changed),
                                       self.key, self.now)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_reject_extra_task_fields_and_invalid_categories(self):
        for mutated in (
            dict(self.task, shell="rm -rf /"),
            dict(self.task, risk="funds_transfer"),
            dict(self.task, workstream="unknown"),
            dict(self.task, acceptance=""),
            dict(self.task, title="a" * 161),
        ):
            with self.subTest(value=mutated):
                with self.assertRaises(bridge.Rejected):
                    bridge.import_task(self.dbfile, self.envelope(task=mutated),
                                       self.key, self.now)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_reject_duplicate_keys_and_oversized_input(self):
        duplicate = (b'{"v":1,"v":1,"id":"a","ts":0,"op":"task.create",'
                     b'"task":{},"sig":"ab"}')
        with self.assertRaises(bridge.Rejected):
            bridge.authenticate(duplicate, self.key, self.now)
        with self.assertRaises(bridge.Rejected):
            bridge.authenticate(b"x" * 8193, self.key, self.now)

    def test_permission_and_symlink_safety(self):
        os.chmod(self.keyfile, 0o644)
        with self.assertRaises(bridge.Rejected):
            bridge.read_key(self.keyfile)
        os.chmod(self.keyfile, 0o600)
        self.assertEqual(bridge.read_key(self.keyfile), self.key)
        link = self.root / "linked-key"
        link.symlink_to(self.keyfile)
        with self.assertRaises(bridge.Rejected):
            bridge.read_key(link)
        with self.assertRaises(bridge.Rejected):
            bridge.init_key(self.keyfile)

    def test_database_absence_fails_closed(self):
        self.dbfile.unlink()
        with self.assertRaises(bridge.Rejected):
            bridge.import_task(self.dbfile, self.envelope(), self.key, self.now)
        self.assertFalse(self.dbfile.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
