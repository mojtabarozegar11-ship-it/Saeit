#!/usr/bin/env python3
"""Isolated rollback regression: never modify live site or customer data.

The release updater is imported but all file operations use a temporary
stand-in for the Ramadan War route. No SSH, network, or payment calls.
"""
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "ramadan_scoped_deploy", Path(__file__).with_name("deploy.py")
)
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


def digest(value):
    return hashlib.sha256(value).hexdigest()


class ScopedRollbackTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.game = self.root / "ramadan-war"
        self.game.mkdir()
        self.stage = self.root / "stage"
        self.stage.mkdir()
        self.protected = self.root / "protected-home.html"
        self.protected.write_bytes(b"protected home unchanged")
        old_game, new_game = deploy.GAME, deploy.ROOT
        deploy.GAME, deploy.ROOT = self.game, self.root
        self.addCleanup(lambda: setattr(deploy, "GAME", old_game))
        self.addCleanup(lambda: setattr(deploy, "ROOT", new_game))
        self.run = "123456"
        self.old = b"old known-good game code"
        self.new = b"new candidate game code"
        (self.stage / "old-game.js").write_bytes(self.old)
        self.metadata = {
            "old": {"game.js": digest(self.old)},
            "new": {"game.js": digest(self.new), "new-asset.js": digest(b"new asset")},
        }

    def test_partial_release_restores_old_and_removes_only_new_asset(self):
        (self.game / "game.js").write_bytes(self.new)
        (self.game / "new-asset.js").write_bytes(b"new asset")
        deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertEqual((self.game / "game.js").read_bytes(), self.old)
        self.assertFalse((self.game / "new-asset.js").exists())
        self.assertEqual(self.protected.read_bytes(), b"protected home unchanged")

    def test_rollback_is_idempotent(self):
        (self.game / "game.js").write_bytes(self.new)
        (self.game / "new-asset.js").write_bytes(b"new asset")
        deploy.rollback_files(self.stage, self.metadata, self.run)
        deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertEqual((self.game / "game.js").read_bytes(), self.old)
        self.assertFalse((self.game / "new-asset.js").exists())

    def test_concurrent_unexpected_modifications_are_preserved(self):
        (self.game / "game.js").write_bytes(b"newer publisher's version")
        (self.game / "new-asset.js").write_bytes(b"newer publisher's asset")
        deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertEqual((self.game / "game.js").read_bytes(), b"newer publisher's version")
        self.assertEqual((self.game / "new-asset.js").read_bytes(), b"newer publisher's asset")

    def test_rollback_refuses_symlinked_asset(self):
        outside = self.root / "outside-game.js"
        outside.write_bytes(self.new)
        (self.game / "game.js").symlink_to(outside)
        deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertTrue((self.game / "game.js").is_symlink())
        self.assertEqual(outside.read_bytes(), self.new)

    def test_atomic_rejects_path_outside_game(self):
        with self.assertRaises(AssertionError):
            deploy.atomic(self.protected, b"malicious", self.run)
        self.assertEqual(self.protected.read_bytes(), b"protected home unchanged")

    def test_atomic_rejects_symlinked_game_directory(self):
        other = self.root / "other"
        other.mkdir()
        (self.game / "three-addons").symlink_to(other, target_is_directory=True)
        with self.assertRaises(AssertionError):
            deploy.atomic(self.game / "three-addons" / "loader.js", b"escape", self.run)
        self.assertFalse((other / "loader.js").exists())

    def test_atomic_rejects_symlinked_leaf(self):
        outside = self.root / "outside.txt"
        outside.write_bytes(b"keep")
        (self.game / "game.js").symlink_to(outside)
        with self.assertRaises(AssertionError):
            deploy.atomic(self.game / "game.js", b"overwrite", self.run)
        self.assertEqual(outside.read_bytes(), b"keep")

    def test_atomic_rejects_preexisting_temp_file(self):
        path = self.game / "game.js"
        path.write_bytes(self.old)
        pending = self.game / (".game.js.ramadan-" + self.run)
        pending.write_bytes(b"other run's temporary data")
        with self.assertRaises(AssertionError):
            deploy.atomic(path, self.new, self.run)
        self.assertEqual(path.read_bytes(), self.old)
        self.assertEqual(pending.read_bytes(), b"other run's temporary data")

    def test_atomic_success_is_scoped_and_exact(self):
        path = self.game / "game.js"
        path.write_bytes(self.old)
        deploy.atomic(path, self.new, self.run)
        self.assertEqual(path.read_bytes(), self.new)
        self.assertEqual(self.protected.read_bytes(), b"protected home unchanged")


if __name__ == "__main__":
    unittest.main()
