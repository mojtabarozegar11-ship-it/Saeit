"""Read-only-in-production rollback tests using an isolated temporary game route."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ramadan_deploy", HERE / "deploy.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class ScopedRollbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / "game"
        self.stage = self.root / "stage"
        self.game.mkdir()
        self.stage.mkdir()
        self.old = b"old-known-good-client"
        self.new = b"new-game-client"
        self.module = b"new-es-module"
        (self.game / "game.js").write_bytes(self.new)
        (self.game / "policy.mjs").write_bytes(self.module)
        (self.stage / "old-game.js").write_bytes(self.old)
        self.manifest = {
            "old": {"game.js": deploy.digest(self.old)},
            "new": {
                "game.js": deploy.digest(self.new),
                "policy.mjs": deploy.digest(self.module),
            },
        }
        self.guard = patch.object(deploy, "GAME", self.game)
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def rollback(self):
        deploy.rollback_files(self.stage, self.manifest, "123456")

    def test_valid_backup_restores_existing_client_and_removes_new_module(self):
        self.rollback()
        self.assertEqual((self.game / "game.js").read_bytes(), self.old)
        self.assertFalse((self.game / "policy.mjs").exists())
        self.rollback()
        self.assertEqual((self.game / "game.js").read_bytes(), self.old)

    def test_corrupt_backup_never_overwrites_live_client(self):
        (self.stage / "old-game.js").write_bytes(b"damaged-or-truncated-backup")
        self.rollback()
        self.assertEqual((self.game / "game.js").read_bytes(), self.new)

    def test_missing_backup_never_overwrites_live_client(self):
        (self.stage / "old-game.js").unlink()
        self.rollback()
        self.assertEqual((self.game / "game.js").read_bytes(), self.new)

    def test_concurrent_live_edit_is_preserved(self):
        concurrent = b"newer-edit-by-another-operator"
        (self.game / "game.js").write_bytes(concurrent)
        self.rollback()
        self.assertEqual((self.game / "game.js").read_bytes(), concurrent)

    def test_symlinked_backup_is_rejected(self):
        (self.stage / "old-game.js").unlink()
        target = self.root / "outside.txt"
        target.write_bytes(self.old)
        (self.stage / "old-game.js").symlink_to(target)
        self.rollback()
        self.assertEqual((self.game / "game.js").read_bytes(), self.new)
        self.assertEqual(target.read_bytes(), self.old)


if __name__ == "__main__":
    unittest.main()
