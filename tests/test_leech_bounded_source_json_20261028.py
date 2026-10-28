"""Synthetic read-only regression tests for WO-26102501 source JSON.

No private VPS manuscript, cron, lock, network or paid API is accessed.
"""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/factory_leech_free_offline_original_author_20261025.py"
SPEC = importlib.util.spec_from_file_location("leech_bounded_source_json", SCRIPT)
author = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(author)


class SafeJsonBoundedTests(unittest.TestCase):
    def test_valid_utf8_object_and_exact_byte_limit_are_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.json"
            path.write_text(json.dumps({"title": "café — validated"}), encoding="utf-8")
            before = (path.read_bytes(), path.stat().st_mtime_ns)
            self.assertEqual(author.safe_json(path), {"title": "café — validated"})
            self.assertEqual(author.safe_json(path, max_bytes=len(before[0])), {"title": "café — validated"})
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_symlink_is_never_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "outside.json"
            target.write_text('{"private": "synthetic"}', encoding="utf-8")
            link = root / "source.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(RuntimeError, "MISSING_OR_UNSAFE_JSON"):
                author.safe_json(link)
            self.assertEqual(target.read_text(encoding="utf-8"), '{"private": "synthetic"}')

    def test_symlink_swap_at_open_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "source.json"
            outside = root / "outside.json"
            path.write_text('{"safe": true}', encoding="utf-8")
            outside.write_text('{"secret": "synthetic"}', encoding="utf-8")
            actual_open = os.open

            def swap_open(candidate, flags, *args, **kwargs):
                if candidate == "source.json" and kwargs.get("dir_fd") is not None:
                    path.unlink()
                    path.symlink_to(outside)
                return actual_open(candidate, flags, *args, **kwargs)

            with mock.patch.object(os, "open", swap_open):
                with self.assertRaisesRegex(RuntimeError, "MISSING_OR_UNSAFE_JSON"):
                    author.safe_json(path)
            self.assertEqual(outside.read_text(encoding="utf-8"), '{"secret": "synthetic"}')

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO required")
    def test_fifo_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.json"
            os.mkfifo(path, 0o600)
            with self.assertRaisesRegex(RuntimeError, "MISSING_OR_UNSAFE_JSON"):
                author.safe_json(path)

    def test_growth_after_stale_fstat_is_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.json"
            path.write_bytes(b'{"a":"' + b"x" * 2000 + b'"}')
            real_fstat = os.fstat

            def stale_fstat(fd):
                current = list(real_fstat(fd)[:10])
                current[6] = 10
                return os.stat_result(current)

            with mock.patch.object(os, "fstat", stale_fstat):
                with self.assertRaisesRegex(RuntimeError, "MISSING_OR_UNSAFE_JSON"):
                    author.safe_json(path, max_bytes=128)
            self.assertGreater(path.stat().st_size, 128)

    def test_invalid_utf8_invalid_json_and_non_object_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.json"
            for raw in (b'{"a":"\\xff"}', b'{"a":', b"[]"):
                if raw == b'{"a":"\\xff"}':
                    raw = b'{"a":"' + bytes([255]) + b'"}'
                path.write_bytes(raw)
                with self.assertRaises(RuntimeError):
                    author.safe_json(path)
                self.assertEqual(path.read_bytes(), raw)

    def test_one_byte_over_limit_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.json"
            path.write_bytes(b'{"a":1}')
            self.assertEqual(author.safe_json(path, max_bytes=7), {"a": 1})
            with self.assertRaisesRegex(RuntimeError, "MISSING_OR_UNSAFE_JSON"):
                author.safe_json(path, max_bytes=6)


    def test_in_place_rewrite_detected_by_second_fstat(self):
        """A pinned inode is not immutable: reject changed metadata mid-read."""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.json"
            path.write_text('{"safe": true}', encoding="utf-8")
            original = path.read_bytes()
            actual_fstat = os.fstat
            calls = 0

            def changed_fstat(fd):
                nonlocal calls
                calls += 1
                metadata = actual_fstat(fd)
                if calls == 2:
                    from types import SimpleNamespace
                    return SimpleNamespace(
                        st_mode=metadata.st_mode, st_dev=metadata.st_dev,
                        st_ino=metadata.st_ino, st_size=metadata.st_size,
                        st_mtime_ns=metadata.st_mtime_ns + 1,
                        st_ctime_ns=metadata.st_ctime_ns)
                return metadata

            with mock.patch.object(os, "fstat", changed_fstat):
                with self.assertRaisesRegex(RuntimeError, "SOURCE_JSON_CHANGED_DURING_READ"):
                    author.safe_json(path)
            self.assertGreaterEqual(calls, 2)
            self.assertEqual(path.read_bytes(), original)

    def test_symlinked_ancestor_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outside = root / "outside"
            outside.mkdir()
            (outside / "source.json").write_text('{"secret": true}', encoding="utf-8")
            (root / "linked").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "MISSING_OR_UNSAFE_JSON"):
                author.safe_json(root / "linked" / "source.json")

    def test_ancestor_swap_after_dirfd_open_reads_pinned_original_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            parent = root / "parent"
            moved = root / "parent-original"
            outside = root / "outside"
            parent.mkdir()
            outside.mkdir()
            (parent / "source.json").write_text('{"safe": true}', encoding="utf-8")
            (outside / "source.json").write_text('{"secret": true}', encoding="utf-8")
            actual_open = os.open
            swapped = False

            def swap_after_parent_open(candidate, flags, *args, **kwargs):
                nonlocal swapped
                if candidate == "source.json" and not swapped:
                    swapped = True
                    parent.rename(moved)
                    parent.symlink_to(outside, target_is_directory=True)
                return actual_open(candidate, flags, *args, **kwargs)

            with mock.patch.object(os, "open", swap_after_parent_open):
                result = author.safe_json(parent / "source.json")
            self.assertTrue(swapped)
            self.assertEqual(result, {"safe": True})
            self.assertEqual((outside / "source.json").read_text(encoding="utf-8"),
                             '{"secret": true}')


if __name__ == "__main__":
    unittest.main()
