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
        self.assets_guard = patch.object(deploy, "ASSETS", ["game.js", "policy.mjs"])
        self.assets_guard.start()
        self.addCleanup(self.assets_guard.stop)

    def rollback(self):
        return deploy.rollback_files(self.stage, self.manifest, "123456")

    def test_valid_backup_restores_existing_client_and_removes_new_module(self):
        self.assertTrue(self.rollback())
        self.assertEqual((self.game / "game.js").read_bytes(), self.old)
        self.assertFalse((self.game / "policy.mjs").exists())
        self.assertTrue(self.rollback())
        self.assertEqual((self.game / "game.js").read_bytes(), self.old)

    def test_corrupt_backup_never_overwrites_live_client(self):
        (self.stage / "old-game.js").write_bytes(b"damaged-or-truncated-backup")
        self.assertFalse(self.rollback())
        self.assertEqual((self.game / "game.js").read_bytes(), self.new)
        self.assertEqual((self.game / "policy.mjs").read_bytes(), self.module)

    def test_missing_backup_never_overwrites_live_client(self):
        (self.stage / "old-game.js").unlink()
        self.assertFalse(self.rollback())
        self.assertEqual((self.game / "game.js").read_bytes(), self.new)
        self.assertEqual((self.game / "policy.mjs").read_bytes(), self.module)

    def test_concurrent_live_edit_is_preserved(self):
        concurrent = b"newer-edit-by-another-operator"
        (self.game / "game.js").write_bytes(concurrent)
        self.assertFalse(self.rollback())
        self.assertEqual((self.game / "game.js").read_bytes(), concurrent)
        self.assertEqual((self.game / "policy.mjs").read_bytes(), self.module)

    def test_symlinked_backup_is_rejected(self):
        (self.stage / "old-game.js").unlink()
        target = self.root / "outside.txt"
        target.write_bytes(self.old)
        (self.stage / "old-game.js").symlink_to(target)
        self.assertFalse(self.rollback())
        self.assertEqual((self.game / "game.js").read_bytes(), self.new)
        self.assertEqual((self.game / "policy.mjs").read_bytes(), self.module)
        self.assertEqual(target.read_bytes(), self.old)
        self.assertEqual((self.game / "policy.mjs").read_bytes(), self.module)


    def test_unexpected_new_asset_blocks_entire_rollback(self):
        (self.game / "policy.mjs").write_bytes(b"concurrent-new-module")
        self.assertFalse(self.rollback())
        self.assertEqual((self.game / "game.js").read_bytes(), self.new)
        self.assertEqual((self.game / "policy.mjs").read_bytes(), b"concurrent-new-module")

    def test_invalid_manifest_blocks_entire_rollback(self):
        self.manifest["new"]["unexpected.js"] = deploy.digest(b"bad")
        self.assertFalse(self.rollback())
        self.assertEqual((self.game / "game.js").read_bytes(), self.new)
        self.assertEqual((self.game / "policy.mjs").read_bytes(), self.module)


    def test_existing_atomic_temp_aborts_before_any_live_file_changes(self):
        temp_path = self.game / ".game.js.ramadan-123456"
        temp_path.write_bytes(b"operator-owned-temporary-file")
        self.assertFalse(self.rollback())
        self.assertEqual((self.game / "game.js").read_bytes(), self.new)
        self.assertEqual((self.game / "policy.mjs").read_bytes(), self.module)
        self.assertEqual(temp_path.read_bytes(), b"operator-owned-temporary-file")

    def test_symlinked_nested_backup_directory_is_rejected(self):
        nested = "three-addons/foo.js"
        old_nested = b"old-nested-file"
        new_nested = b"new-nested-file"
        live_nested = self.game / nested
        live_nested.parent.mkdir()
        live_nested.write_bytes(new_nested)
        self.manifest["old"][nested] = deploy.digest(old_nested)
        self.manifest["new"][nested] = deploy.digest(new_nested)
        deploy.ASSETS.append(nested)
        outside = self.root / "outside-backups"
        outside.mkdir()
        (outside / "foo.js").write_bytes(old_nested)
        (self.stage / "old-three-addons").symlink_to(outside, target_is_directory=True)
        self.assertFalse(self.rollback())
        self.assertEqual((self.game / "game.js").read_bytes(), self.new)
        self.assertEqual(live_nested.read_bytes(), new_nested)
        self.assertEqual((self.game / "policy.mjs").read_bytes(), self.module)



if __name__ == "__main__":
    unittest.main()
