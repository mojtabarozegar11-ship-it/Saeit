import json
import tempfile
from pathlib import Path
from unittest import TestCase
from scripts.mpw_reconcile_scheduler import read_cursor, store_cursor, validate_result


class ReconcileSchedulerTests(TestCase):
    def test_cursor_survives_and_wraps(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/"cursor.json"
            self.assertEqual(read_cursor(p), 0)
            store_cursor(p, 42)
            self.assertEqual(read_cursor(p), 42)
            store_cursor(p, 0)
            self.assertEqual(read_cursor(p), 0)

    def test_symlink_cursor_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/"cursor.json"
            target = Path(directory)/"target"
            target.write_text("0")
            p.symlink_to(target)
            with self.assertRaises(OSError):
                read_cursor(p)

    def test_continuation_must_advance(self):
        raw = json.dumps(dict(scanned=3, paid=1, pending=1, deferred=1, next_after_id=42))
        self.assertEqual(validate_result(raw, 41, 3)["next_after_id"], 42)
        with self.assertRaises(ValueError):
            validate_result(raw, 42, 3)

    def test_short_batch_wraps(self):
        raw = json.dumps(dict(scanned=2, paid=0, pending=1, deferred=1, next_after_id=0))
        self.assertEqual(validate_result(raw, 42, 3)["next_after_id"], 0)

    def test_inconsistent_batch_rejected(self):
        raw = json.dumps(dict(scanned=2, paid=2, pending=1, deferred=0, next_after_id=0))
        with self.assertRaises(ValueError):
            validate_result(raw, 0, 3)
