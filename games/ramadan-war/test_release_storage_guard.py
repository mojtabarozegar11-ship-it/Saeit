#!/usr/bin/env python3
"""Offline capacity-gate regressions. No network, VPS, cPanel or site writes."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location(
    "ramadan_storage_guard", Path(__file__).with_name("release_storage_guard.py")
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class StorageGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.stage = self.root / "staging"
        self.game = self.root / "public_html" / "ramadan-war"
        self.stage.mkdir()
        self.game.mkdir(parents=True)
        self.payload = 10 * 1024 * 1024
        self.reserve = 512 * 1024 * 1024

    def free(self, bytes_available):
        return lambda _: SimpleNamespace(f_bavail=bytes_available, f_frsize=1)

    def test_ample_shared_space_passes_without_writing(self):
        before = sorted(str(p) for p in self.root.rglob("*"))
        self.assertTrue(guard.check_capacity(
            self.stage, self.game, self.payload,
            statvfs=self.free(self.reserve + 4 * self.payload + 1)))
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob("*")))

    def test_zero_space_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "shared release filesystem"):
            guard.check_capacity(self.stage, self.game, self.payload,
                                 statvfs=self.free(0))

    def test_shared_mount_counts_stage_backup_and_atomic_writes_together(self):
        with self.assertRaisesRegex(RuntimeError, "shared release filesystem"):
            guard.check_capacity(self.stage, self.game, self.payload,
                                 statvfs=self.free(self.reserve + 3 * self.payload))

    def test_separate_mount_checks_both_independently(self):
        free = lambda p: SimpleNamespace(
            f_bavail=(self.reserve + 2 * self.payload + 1)
            if p == self.stage else (self.reserve + 2 * self.payload - 1),
            f_frsize=1)
        with self.assertRaisesRegex(RuntimeError, "live game filesystem"):
            guard.check_capacity(self.stage, self.game, self.payload,
                                 statvfs=free,
                                 device=lambda p: 1 if p == self.stage else 2)

    def test_symlinked_game_route_fails_closed(self):
        other = self.root / "other"
        other.mkdir()
        self.game.rmdir()
        self.game.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "linked"):
            guard.check_capacity(self.stage, self.game, self.payload,
                                 statvfs=self.free(10**10))

    def test_bad_payload_fails_closed(self):
        for payload in (0, -1, 1 << 40, "100"):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    guard.check_capacity(self.stage, self.game, payload,
                                         statvfs=self.free(10**10))


if __name__ == "__main__":
    unittest.main()
