"""Regression: leech WO-26102501 status must remain read-only and fail closed.

These tests use synthetic text under a temporary directory; they never access
the VPS manuscript, change the one-minute cron, or acquire a writer lock.
"""
import contextlib
import importlib.util
import io
import json
import os
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

    def test_part_growth_after_stat_is_rejected_by_bounded_actual_read(self):
        with tempfile.TemporaryDirectory() as temp:
            private = Path(temp) / "private"
            private.mkdir()
            part = private / "chapter-01-part-001.md"
            part.write_bytes(b"A" * 50001)
            real_stat = Path.stat

            def stale_stat(path, *args, **kwargs):
                result = real_stat(path, *args, **kwargs)
                if path == part:
                    fields = list(result[:10])
                    fields[6] = 1000  # A stale precheck sees an eligible file.
                    return os.stat_result(fields)
                return result

            with (mock.patch.object(author, "PRIVATE", private),
                  mock.patch.object(Path, "stat", stale_stat)):
                with self.assertRaisesRegex(RuntimeError, "UNEXPECTED_PRIVATE_MANUSCRIPT_ENTRY"):
                    author.list_parts()
            self.assertEqual(part.stat().st_size, 50001)

    def test_symlink_swap_between_preflight_and_open_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            private = base / "private"
            private.mkdir()
            part = private / "chapter-01-part-001.md"
            target = base / "outside.md"
            part.write_text("Safe original manuscript segment. " * 20, encoding="utf-8")
            target.write_text("Do not follow this synthetic target.", encoding="utf-8")
            original_open = os.open

            def swapped_open(path, flags, *args, **kwargs):
                if Path(path) == part:
                    part.unlink()
                    part.symlink_to(target)
                return original_open(path, flags, *args, **kwargs)

            with (mock.patch.object(author, "PRIVATE", private),
                  mock.patch.object(os, "open", swapped_open)):
                with self.assertRaisesRegex(RuntimeError, "UNSAFE_PRIVATE_MANUSCRIPT_IO"):
                    author.list_parts()
            self.assertEqual(target.read_text(encoding="utf-8"),
                             "Do not follow this synthetic target.")

    def test_fifo_swap_between_preflight_and_open_fails_without_hanging(self):
        with tempfile.TemporaryDirectory() as temp:
            private=Path(temp)/"private"
            private.mkdir()
            part=private/"chapter-01-part-001.md"
            part.write_text("Synthetic manuscript content. "*20,encoding="utf-8")
            original_open=os.open

            def replace_with_fifo(path,flags,*args,**kwargs):
                if Path(path)==part:
                    part.unlink()
                    os.mkfifo(part,0o600)
                return original_open(path,flags,*args,**kwargs)

            with (mock.patch.object(author,"PRIVATE",private),
                  mock.patch.object(os,"open",replace_with_fifo)):
                with self.assertRaisesRegex(RuntimeError,"UNEXPECTED_PRIVATE_MANUSCRIPT_ENTRY"):
                    author.list_parts()
            self.assertTrue(part.exists())
            self.assertFalse(part.is_file())
            self.assertFalse((private/".authoring.lock").exists())

    def test_exact_50000_byte_manuscript_is_accepted_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            private=Path(temp)/"private"
            private.mkdir()
            part=private/"chapter-01-part-001.md"
            part.write_bytes(b"A"*50000)
            before=(part.read_bytes(),part.stat().st_mtime_ns)
            with mock.patch.object(author,"PRIVATE",private):
                chunks=author.list_parts()
            self.assertEqual(len(chunks[1]),1)
            self.assertEqual(len(chunks[1][0][1].encode("utf-8")),50000)
            self.assertEqual((part.read_bytes(),part.stat().st_mtime_ns),before)
            self.assertFalse((private/".authoring.lock").exists())

    def test_valid_multibyte_utf8_part_is_read_without_rewriting(self):
        with tempfile.TemporaryDirectory() as temp:
            private=Path(temp)/"private"
            private.mkdir()
            part=private/"chapter-01-part-001.md"
            prose=("Scientific observations of leech husbandry — café 🌱. "*12)
            part.write_text(prose,encoding="utf-8")
            original=part.read_bytes()
            self.assertGreater(len(original),200)
            with mock.patch.object(author,"PRIVATE",private):
                chunks=author.list_parts()
            self.assertEqual(chunks[1][0][1],prose)
            self.assertEqual(part.read_bytes(),original)

    def test_invalid_utf8_part_fails_closed_without_mutating_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            private = Path(temp) / "private"
            private.mkdir()
            part = private / "chapter-01-part-001.md"
            part.write_bytes(b"\xff" * 300)
            before = part.read_bytes()
            with mock.patch.object(author, "PRIVATE", private):
                with self.assertRaisesRegex(RuntimeError, "UNSAFE_PRIVATE_MANUSCRIPT_IO"):
                    author.list_parts()
            self.assertEqual(part.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
