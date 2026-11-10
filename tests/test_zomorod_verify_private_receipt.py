"""No-network contract tests for the private, read-only receipt verifier."""

from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "scripts/zomorod_verify_private_receipt.py"
SPEC = importlib.util.spec_from_file_location("zmr_receipt_verifier", SOURCE)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)
COMMAND_ID = "fedcba9876543210fedcba9876543210"


class ReceiptVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "command-center.sqlite3"
        with sqlite3.connect(self.db_path) as db:
            db.executescript("""
                CREATE TABLE bridge_receipts (id TEXT PRIMARY KEY, task_id INTEGER);
                CREATE TABLE tasks (id INTEGER PRIMARY KEY, actor_id INTEGER, request_key TEXT);
                CREATE TABLE task_quality (task_id INTEGER);
                CREATE TABLE task_events (task_id INTEGER, actor_id INTEGER, kind TEXT);
            """)
            db.execute("INSERT INTO bridge_receipts VALUES (?, 77)", (COMMAND_ID,))
            db.execute("INSERT INTO tasks VALUES (77, 0, ?)", (COMMAND_ID,))
            db.execute("INSERT INTO task_quality VALUES (77)")
            db.execute("INSERT INTO task_events VALUES (77, 0, 'bridge_signed_task')")
        os.chmod(self.db_path, 0o600)
        self.owner_patch = patch.object(
            verifier.pwd, "getpwuid", return_value=SimpleNamespace(pw_name="zomorod2")
        )
        self.owner_patch.start()
        self.addCleanup(self.owner_patch.stop)

    def test_authenticated_receipt_readback_without_db_change(self):
        with sqlite3.connect(self.db_path) as db:
            before = db.total_changes, db.execute("SELECT COUNT(*) FROM task_events").fetchone()[0]
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            verifier.verify_receipt(self.db_path, COMMAND_ID)
        result = buffer.getvalue()
        self.assertIn("PRIVATE_RECEIPT_READBACK=VERIFIED", result)
        self.assertIn("COMMAND_EXECUTION=NOT_CLAIMED", result)
        self.assertNotIn(COMMAND_ID, result)
        with sqlite3.connect(self.db_path) as db:
            after = db.total_changes, db.execute("SELECT COUNT(*) FROM task_events").fetchone()[0]
        self.assertEqual(before, after)

    def test_missing_signed_event_fails_closed(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("DELETE FROM task_events")
        with self.assertRaisesRegex(verifier.VerificationError, "RECEIPT_NOT_INDEPENDENTLY_VERIFIED"):
            verifier.verify_receipt(self.db_path, COMMAND_ID)

    def test_other_command_id_not_accepted(self):
        with self.assertRaisesRegex(verifier.VerificationError, "RECEIPT_NOT_INDEPENDENTLY_VERIFIED"):
            verifier.verify_receipt(self.db_path, "a" * 32)

    def test_invalid_id_rejected_before_database_read(self):
        with self.assertRaisesRegex(verifier.VerificationError, "COMMAND_ID_INVALID"):
            verifier.verify_receipt(self.db_path, "untrusted-id")

    def test_world_readable_database_rejected(self):
        os.chmod(self.db_path, 0o644)
        with self.assertRaisesRegex(verifier.VerificationError, "PRIVATE_DATABASE_UNSAFE"):
            verifier.verify_receipt(self.db_path, COMMAND_ID)

    def test_symlink_database_rejected(self):
        link = Path(self.temp.name) / "symlink.db"
        link.symlink_to(self.db_path)
        with self.assertRaisesRegex(verifier.VerificationError, "PRIVATE_DATABASE_UNSAFE"):
            verifier.verify_receipt(link, COMMAND_ID)


if __name__ == "__main__":
    unittest.main()
