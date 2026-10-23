"""Regression tests for Stage4 persisted retry eligibility and safety guards."""
import datetime as dt
import importlib.util
from pathlib import Path
import tempfile
import unittest


FILE = (Path(__file__).resolve().parents[1] / "scripts"
        / "factory_stage4_due_dispatch_20261023.py")
spec = importlib.util.spec_from_file_location("stage4_due_dispatch", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RetryEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 10, 23, 12, tzinfo=dt.timezone.utc)

    def stage(self, date, status="waiting_for_evidence"):
        return {"validation": {"stage4_research": {
            "status": status, "next_retry_at": date}}}

    def test_due_and_overdue_are_eligible(self):
        self.assertEqual(module.due_retry(
            self.stage("2026-10-23T12:00:00+00:00"), self.now), self.now)
        self.assertLess(module.due_retry(
            self.stage("2026-10-22T01:00:00Z"), self.now), self.now)

    def test_future_retry_is_not_eligible(self):
        self.assertIsNone(module.due_retry(
            self.stage("2026-10-24T12:00:00+00:00"), self.now))

    def test_exhausted_capacity_cannot_be_bypassed(self):
        self.assertIsNone(module.due_retry(
            self.stage("2026-10-21T01:00:00Z", "capacity_exhausted"), self.now))

    def test_invalid_and_unsafe_timestamps_fail_closed(self):
        for stamp in (None, "", "sometime", "2026-10-22T12:00:00", "0" * 300):
            with self.subTest(stamp=stamp):
                self.assertIsNone(module.due_retry(self.stage(stamp), self.now))

    def test_invalid_metadata_fails_closed(self):
        for metadata in (None, [], {}, {"validation": "bad"},
                         {"validation": {"stage4_research": []}}):
            with self.subTest(metadata=metadata):
                self.assertIsNone(module.due_retry(metadata, self.now))

    def test_only_safe_database_error_codes_are_reported(self):
        self.assertEqual(module.safe_error_code(Exception(1213, "private database info")), "1213")
        self.assertEqual(module.safe_error_code(Exception("database is locked")), "sqlite_locked")
        self.assertEqual(module.safe_error_code(Exception("password=secret in SQL")), "unspecified")


class FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, **conditions):
        if "pk__gt" in conditions:
            return FakeRows([row for row in self.rows if row[0] > conditions["pk__gt"]])
        return FakeRows([row for row in self.rows if row[0] <= conditions["pk__lte"]])

    def order_by(self, field):
        assert field == "pk"
        return FakeRows(sorted(self.rows))

    def values_list(self, *fields):
        assert fields == ("pk", "metadata")
        return self.rows


class CursorFairnessTests(unittest.TestCase):
    def test_one_thousand_twenty_nine_products_all_get_a_turn(self):
        manager = FakeRows([(pk, {}) for pk in range(1, 1030)])
        cursor = 0
        seen = set()
        for _ in range(3):
            page = module.candidate_window(manager, cursor, 500)
            ids = [pk for pk, _ in page]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(len(ids), 500)
            seen.update(ids)
            cursor = ids[-1]
        self.assertEqual(len(seen), 1029)

    def test_cursor_survives_restart_and_wraps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(module.read_cursor(root), 0)
            module.write_cursor(root, 1000)
            self.assertEqual(module.read_cursor(root), 1000)
            manager = FakeRows([(pk, {}) for pk in (1, 2, 1001, 1002)])
            self.assertEqual([pk for pk, _ in module.candidate_window(manager, 1000, 3)],
                             [1001, 1002, 1])

    def test_corrupt_or_symlink_cursor_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "stage4-due-dispatch.cursor.json"
            path.write_text('{"schema":"unknown","last_pk":999}')
            with self.assertRaisesRegex(RuntimeError, "CURSOR_INVALID"):
                module.read_cursor(root)
            path.unlink()
            path.symlink_to(root / "missing")
            with self.assertRaisesRegex(RuntimeError, "CURSOR_SYMLINK"):
                module.read_cursor(root)
            with self.assertRaisesRegex(RuntimeError, "CURSOR_SYMLINK"):
                module.write_cursor(root, 5)


if __name__ == "__main__":
    unittest.main()
