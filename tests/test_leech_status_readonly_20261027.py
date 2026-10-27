"""Regression: leech WO-26102501 status must remain read-only and fail closed.

These tests use synthetic text under a temporary directory; they never access
the VPS manuscript, change the one-minute cron, or acquire a writer lock.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/factory_leech_free_offline_original_author_20261025.py"
SPEC = importlib.util.spec_from_file_location("leech_status_readonly_guard", SCRIPT)
author = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(author)


class LeechStatusReadOnlyTests(unittest.TestCase):
    def test_status_counts_only_substantive_words_without_mutating_private_files(self):
        with tempfile.TemporaryDirectory() as temp:
            private = Path(temp) / "private"
            private.mkdir()
            part = private / "chapter-01-part-001.md"
            part.write_text(
                "# This heading is excluded from the substantive count\n"
                + "The farm operator records water conditions and documents "
                  "traceable observations for independent scientific review. " * 8,
                encoding="utf-8",
            )
            expected_words = len(author.words(part.read_text(encoding="utf-8")))
            before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                      for p in private.iterdir()}
            out = io.StringIO()
            with (mock.patch.object(author, "PRIVATE", private),
                  mock.patch.object(author, "source_evidence", return_value=({}, [], [])),
                  mock.patch.object(sys, "argv", [str(SCRIPT), "status"]),
                  contextlib.redirect_stdout(out)):
                author.main()
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["order_id"], "WO-26102501")
            self.assertEqual(payload["verified_unreviewed_prose_words"], expected_words)
            self.assertEqual(payload["next_chapter"], 1)
            self.assertFalse(payload["quality1000_approved"])
            after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                     for p in private.iterdir()}
            self.assertEqual(before, after)
            self.assertFalse((private / ".authoring.lock").exists())
            self.assertFalse((private / "status.json").exists())

    def test_status_rejects_private_symlink_without_following_it(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            target = base / "outside.md"
            target.write_text("Confidential synthetic placeholder", encoding="utf-8")
            private = base / "private"
            private.mkdir()
            (private / "chapter-01-part-001.md").symlink_to(target)
            with mock.patch.object(author, "PRIVATE", private):
                with self.assertRaisesRegex(RuntimeError, "UNEXPECTED_PRIVATE_MANUSCRIPT_ENTRY"):
                    author.list_parts()
            self.assertEqual(target.read_text(encoding="utf-8"),
                             "Confidential synthetic placeholder")


if __name__ == "__main__":
    unittest.main()
