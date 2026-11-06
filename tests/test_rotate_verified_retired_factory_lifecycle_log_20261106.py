"""Synthetic acceptance of the one-time reversible factory log rotation."""
import gzip
import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = (Path(__file__).resolve().parents[1] / "scripts"
          / "rotate_verified_retired_factory_lifecycle_log_20261106.py")
spec = importlib.util.spec_from_file_location("safe_factory_rotate", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SafeFactoryLogRotationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "operations"
        self.root.mkdir()
        self.log = self.root / module.LOG_NAME
        self.original = (b"old verified log text\n" * 1024) + b"END"
        self.log.write_bytes(self.original)
        self.lock = self.root / module.LOCK_NAME
        self.lock.write_bytes(b"")
        older = time.time() - 9 * 86400
        os.utime(self.log, (older, older))
        p = mock.patch.object(module, "EXPECTED_TARGET_SIZE", len(self.original))
        p.start()
        self.addCleanup(p.stop)

    def test_dry_run_never_changes_source_or_writes_archive(self):
        before = self.log.stat()
        report = module.rotate(root=self.root)
        self.assertEqual(report["mode"], "dry_run")
        self.assertEqual(self.log.read_bytes(), self.original)
        self.assertEqual(self.log.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertFalse((self.root / module.ARCHIVE_NAME).exists())

    def test_apply_verifies_gzip_and_preserves_source_inode_and_path(self):
        before = self.log.stat()
        with mock.patch.object(module, "STABILITY_SECONDS", 0):
            report = module.rotate(root=self.root, apply=True)
        archive = self.root / module.ARCHIVE_NAME
        self.assertTrue(report["archive_created"])
        self.assertTrue(report["source_truncated"])
        self.assertGreater(report["estimated_reclaimed_bytes"], 0)
        self.assertEqual(self.log.stat().st_ino, before.st_ino)
        self.assertEqual(self.log.read_bytes(), b"")
        with gzip.open(archive, "rb") as source:
            self.assertEqual(source.read(), self.original)
        self.assertFalse(report["factory_services_changed"])
        self.assertFalse(report["other_files_changed"])
        with self.assertRaisesRegex(RuntimeError, "ARCHIVE_ALREADY_EXISTS"):
            module.rotate(root=self.root, apply=True)

    def test_recent_or_wrong_size_log_is_never_rotated(self):
        os.utime(self.log, None)
        with self.assertRaisesRegex(RuntimeError, "RECENTLY_ACTIVE"):
            module.rotate(root=self.root, apply=True)
        self.assertEqual(self.log.read_bytes(), self.original)
        self.log.write_bytes(b"changed")
        with self.assertRaisesRegex(RuntimeError, "SIZE_CHANGED"):
            module.rotate(root=self.root, apply=True)

    def test_locked_or_symlink_target_is_never_rotated(self):
        import fcntl
        with self.lock.open("rb") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "LOCK_BUSY"):
                module.rotate(root=self.root, apply=True)
        self.assertEqual(self.log.read_bytes(), self.original)
        self.log.unlink()
        elsewhere = self.root / "elsewhere.txt"
        elsewhere.write_bytes(self.original)
        self.log.symlink_to(elsewhere)
        with self.assertRaisesRegex(RuntimeError, "SINGLE_REGULAR"):
            module.rotate(root=self.root, apply=True)
        self.assertEqual(elsewhere.read_bytes(), self.original)

    def test_content_mutation_during_stability_wait_aborts_before_archive(self):
        def concurrent_change(_seconds):
            self.log.write_bytes(self.original + b"additional entry")
        with mock.patch.object(module.time, "sleep", side_effect=concurrent_change):
            with self.assertRaisesRegex(RuntimeError, "LOG_CHANGED"):
                module.rotate(root=self.root, apply=True)
        self.assertEqual(self.log.read_bytes(), self.original + b"additional entry")
        self.assertFalse((self.root / module.ARCHIVE_NAME).exists())

    def test_failed_gzip_roundtrip_keeps_full_original_log(self):
        with mock.patch.object(module, "STABILITY_SECONDS", 0), \
                mock.patch.object(module, "_sha_stream", return_value=("bad", 0)):
            with self.assertRaisesRegex(RuntimeError, "GZIP_ROUNDTRIP_FAILED"):
                module.rotate(root=self.root, apply=True)
        self.assertEqual(self.log.read_bytes(), self.original)
        self.assertFalse((self.root / module.ARCHIVE_NAME).exists())


if __name__ == "__main__":
    unittest.main()
