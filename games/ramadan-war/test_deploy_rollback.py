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
from unittest.mock import patch

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
            "new": {"game.js": digest(self.new), "index.html": digest(b"new asset")},
        }

    def test_stage_asset_rejects_linked_intermediate_parent(self):
        incoming = self.stage / "incoming"
        incoming.mkdir()
        outside = self.root / "outside-assets"
        outside.mkdir()
        (outside / "GLTFLoader.js").write_bytes(b"do not publish external asset")
        (incoming / "three-addons").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(AssertionError, "linked release file or parent"):
            deploy.safe_release_file(incoming, "three-addons/GLTFLoader.js")
        self.assertEqual((outside / "GLTFLoader.js").read_bytes(),
                         b"do not publish external asset")

    def test_stage_asset_rejects_linked_incoming_root(self):
        outside = self.root / "outside-stage"
        outside.mkdir()
        (outside / "game.js").write_bytes(self.new)
        (self.stage / "incoming").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(AssertionError, "linked release directory"):
            deploy.safe_release_file(self.stage / "incoming", "game.js")
        self.assertEqual((outside / "game.js").read_bytes(), self.new)

    def test_live_asset_rejects_linked_intermediate_parent(self):
        outside = self.root / "outside-live"
        outside.mkdir()
        (outside / "GLTFLoader.js").write_bytes(self.new)
        (self.game / "three-addons").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(AssertionError, "linked release file or parent"):
            deploy.safe_release_file(self.game, "three-addons/GLTFLoader.js")
        self.assertEqual((outside / "GLTFLoader.js").read_bytes(), self.new)

    def test_release_metadata_rejects_symlink_without_reading_private_file(self):
        outside = self.root / "outside-release.json"
        outside.write_text('{"phase":"published"}', encoding="utf-8")
        (self.stage / "release.json").symlink_to(outside)
        with self.assertRaisesRegex(AssertionError, "linked release file or parent"):
            deploy.metadata(self.stage)
        self.assertEqual(outside.read_text(encoding="utf-8"), '{"phase":"published"}')

    def test_nested_regular_asset_read_remains_supported(self):
        incoming = self.stage / "incoming"
        nested = incoming / "three-addons" / "loaders"
        nested.mkdir(parents=True)
        expected = nested / "GLTFLoader.js"
        expected.write_bytes(self.new)
        self.assertEqual(deploy.safe_release_file(
            incoming, "three-addons/loaders/GLTFLoader.js").read_bytes(), self.new)

    def test_partial_release_restores_old_and_removes_only_new_asset(self):
        (self.game / "game.js").write_bytes(self.new)
        (self.game / "index.html").write_bytes(b"new asset")
        deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertEqual((self.game / "game.js").read_bytes(), self.old)
        self.assertFalse((self.game / "index.html").exists())
        self.assertEqual(self.protected.read_bytes(), b"protected home unchanged")

    def test_rollback_is_idempotent(self):
        (self.game / "game.js").write_bytes(self.new)
        (self.game / "index.html").write_bytes(b"new asset")
        deploy.rollback_files(self.stage, self.metadata, self.run)
        deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertEqual((self.game / "game.js").read_bytes(), self.old)
        self.assertFalse((self.game / "index.html").exists())

    def test_concurrent_unexpected_modifications_are_preserved(self):
        (self.game / "game.js").write_bytes(b"newer publisher's version")
        (self.game / "index.html").write_bytes(b"newer publisher's asset")
        with self.assertRaisesRegex(RuntimeError, "rollback conflict, original asset not restored"):
            deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertEqual((self.game / "game.js").read_bytes(), b"newer publisher's version")
        self.assertEqual((self.game / "index.html").read_bytes(), b"newer publisher's asset")

    def test_rollback_refuses_symlinked_asset(self):
        outside = self.root / "outside-game.js"
        outside.write_bytes(self.new)
        (self.game / "game.js").symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, "linked release asset parent"):
            deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertTrue((self.game / "game.js").is_symlink())
        self.assertEqual(outside.read_bytes(), self.new)

    def test_partial_publish_with_old_file_untouched_is_safe_to_retry(self):
        # Publish failed before changing game.js, but had created index.html.
        (self.game / "game.js").write_bytes(self.old)
        (self.game / "index.html").write_bytes(b"new asset")
        deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertEqual((self.game / "game.js").read_bytes(), self.old)
        self.assertFalse((self.game / "index.html").exists())
        deploy.rollback_files(self.stage, self.metadata, self.run)

    def test_missing_original_asset_is_not_falsely_reported_restored(self):
        (self.game / "index.html").write_bytes(b"new asset")
        with self.assertRaisesRegex(RuntimeError, "original asset not restored"):
            deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertFalse((self.game / "index.html").exists())

    def test_unexpected_new_only_asset_preserved_but_rollback_fails(self):
        (self.game / "game.js").write_bytes(self.old)
        (self.game / "index.html").write_bytes(b"another publisher's file")
        with self.assertRaisesRegex(RuntimeError, "new asset not removed"):
            deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertEqual((self.game / "index.html").read_bytes(), b"another publisher's file")

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

    def test_atomic_rejects_symlink_inserted_at_temp_creation(self):
        # Simulate another writer replacing the old check/write gap.
        # Exclusive creation must refuse the inserted link without touching it.
        target = self.game / "game.js"
        target.write_bytes(self.old)
        pending = self.game / (".game.js.ramadan-" + self.run)
        outside = self.root / "outside-customer-file"
        outside.write_bytes(b"preserve")
        real_open = deploy.os.open

        def race_open(path, flags, mode=0o777):
            if Path(path) == pending:
                pending.symlink_to(outside)
            return real_open(path, flags, mode)

        with patch.object(deploy.os, "open", side_effect=race_open):
            with self.assertRaisesRegex(AssertionError, "temporary path exists"):
                deploy.atomic(target, self.new, self.run)
        self.assertEqual(target.read_bytes(), self.old)
        self.assertEqual(outside.read_bytes(), b"preserve")
        self.assertTrue(pending.is_symlink())

    def test_atomic_new_temp_is_created_with_exclusive_nofollow_flags(self):
        target = self.game / "game.js"
        target.write_bytes(self.old)
        real_open = deploy.os.open
        observed = []

        def checked_open(path, flags, mode=0o777):
            observed.append(flags)
            return real_open(path, flags, mode)

        with patch.object(deploy.os, "open", side_effect=checked_open):
            deploy.atomic(target, self.new, self.run)
        self.assertEqual(target.read_bytes(), self.new)
        self.assertTrue(observed)
        self.assertTrue(observed[0] & deploy.os.O_EXCL)
        self.assertTrue(observed[0] & deploy.os.O_CREAT)
        if hasattr(deploy.os, "O_NOFOLLOW"):
            self.assertTrue(observed[0] & deploy.os.O_NOFOLLOW)

    def test_atomic_success_is_scoped_and_exact(self):
        path = self.game / "game.js"
        path.write_bytes(self.old)
        deploy.atomic(path, self.new, self.run)
        self.assertEqual(path.read_bytes(), self.new)
        self.assertEqual(self.protected.read_bytes(), b"protected home unchanged")


    def test_atomic_write_failure_cleans_own_partial_temp(self):
        target = self.game / "game.js"
        target.write_bytes(self.old)
        pending = self.game / (".game.js.ramadan-" + self.run)
        with patch.object(deploy.os, "fsync", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                deploy.atomic(target, self.new, self.run)
        self.assertEqual(target.read_bytes(), self.old)
        self.assertFalse(pending.exists(), "failed atomic write leaked disk space")

    def test_release_state_rejects_planted_symlink_without_external_write(self):
        outside = self.root / "outside-private-state"
        outside.write_bytes(b"keep private file")
        (self.stage / "release.json.tmp").symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, "temporary file already exists"):
            deploy.store(self.stage, {"phase": "prepared"})
        self.assertEqual(outside.read_bytes(), b"keep private file")
        self.assertTrue((self.stage / "release.json.tmp").is_symlink())

    def test_release_state_fsync_failure_cleans_partial_metadata(self):
        with patch.object(deploy.os, "fsync", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                deploy.store(self.stage, {"phase": "prepared"})
        self.assertFalse((self.stage / "release.json.tmp").exists())
        self.assertFalse((self.stage / "release.json").exists())

    def test_release_state_is_exact_and_rejects_stale_temporary_file(self):
        deploy.store(self.stage, {"phase": "prepared", "new": {"game.js": "sha"}})
        self.assertEqual(deploy.metadata(self.stage)["phase"], "prepared")
        self.assertFalse((self.stage / "release.json.tmp").exists())
        stale = self.stage / "release.json.tmp"
        stale.write_bytes(b"unrelated pending state")
        with self.assertRaisesRegex(RuntimeError, "temporary file already exists"):
            deploy.store(self.stage, {"phase": "published"})
        self.assertEqual(stale.read_bytes(), b"unrelated pending state")
        self.assertEqual(deploy.metadata(self.stage)["phase"], "prepared")

    def valid_release_manifest(self):
        return {
            "phase": "prepared",
            "old": {"game.js": "a" * 64},
            "new": {name: "b" * 64 for name in deploy.ASSETS},
            "route": "c" * 64,
            "protected": {".htaccess": "d" * 64, "store/index.html": "e" * 64},
        }

    def test_valid_release_journal_passes_strict_schema(self):
        self.assertTrue(deploy.validate_release_manifest(self.valid_release_manifest()))

    def test_forged_release_journal_cannot_escape_game_or_protected_paths(self):
        for field, bad_key in (("new", "../outside-private-state"),
                               ("old", "../outside-private-state"),
                               ("protected", "../outside-private-state")):
            with self.subTest(field=field):
                forged = self.valid_release_manifest()
                forged[field][bad_key] = "f" * 64
                with self.assertRaises(AssertionError):
                    deploy.validate_release_manifest(forged)

    def test_publish_and_verify_reject_forged_journal_before_live_reads(self):
        forged = self.valid_release_manifest()
        forged["new"]["../outside-private-state"] = "f" * 64
        deploy.store(self.stage, forged)
        with patch.object(deploy, "live_card_check", side_effect=AssertionError("live touched")):
            with self.assertRaises(AssertionError) as published:
                deploy.publish(self.stage, self.run)
            self.assertNotIn("live touched", str(published.exception))
            with self.assertRaises(AssertionError) as verified:
                deploy.verify(self.stage)
            self.assertNotIn("live touched", str(verified.exception))
        self.assertEqual(self.protected.read_bytes(), b"protected home unchanged")

    def test_original_backup_cannot_overwrite_existing_backup(self):
        path = self.stage / "old-game.js"
        with self.assertRaisesRegex(RuntimeError, "rollback backup already exists"):
            deploy.write_backup(self.stage, "game.js", b"unapproved replacement")
        self.assertEqual(path.read_bytes(), self.old)

    def test_original_backup_rejects_symlinked_nested_parent(self):
        outside = self.root / "outside-backups"
        outside.mkdir()
        (self.stage / "old-three-addons").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(AssertionError, "linked backup parent"):
            deploy.write_backup(self.stage, "three-addons/loaders/GLTFLoader.js", self.new)
        self.assertEqual(list(outside.iterdir()), [])

    def test_original_backup_fsync_failure_does_not_leave_partial_file(self):
        path = self.stage / "old-index.html"
        with patch.object(deploy.os, "fsync", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                deploy.write_backup(self.stage, "index.html", self.new)
        self.assertFalse(path.exists())

    def test_protected_route_verification_accepts_exact_regular_files(self):
        home = self.root / ".htaccess"
        home.write_bytes(b"site policy")
        store = self.root / "store"
        store.mkdir()
        (store / "index.html").write_bytes(b"existing store")
        deploy.verify_protected_pages({
            ".htaccess": digest(b"site policy"),
            "store/index.html": digest(b"existing store"),
        })

    def test_protected_route_verification_rejects_linked_directory(self):
        outside = self.root / "outside-store"
        outside.mkdir()
        (outside / "index.html").write_bytes(b"private data")
        (self.root / "store").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(AssertionError, "linked protected route"):
            deploy.verify_protected_pages({
                "store/index.html": digest(b"private data"),
            })
        self.assertEqual((outside / "index.html").read_bytes(), b"private data")

    def test_corrupt_backup_never_replaces_known_good_file(self):
        (self.game / "game.js").write_bytes(self.new)
        (self.stage / "old-game.js").write_bytes(b"corrupt backup")
        with self.assertRaisesRegex(RuntimeError, "backup SHA-256 mismatch"):
            deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertEqual((self.game / "game.js").read_bytes(), self.new)

    def test_bad_backup_does_not_prevent_removing_an_exact_new_asset(self):
        (self.game / "game.js").write_bytes(self.new)
        (self.game / "index.html").write_bytes(b"new asset")
        (self.stage / "old-game.js").write_bytes(b"corrupt backup")
        with self.assertRaisesRegex(RuntimeError, "backup SHA-256 mismatch"):
            deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertEqual((self.game / "game.js").read_bytes(), self.new)
        self.assertFalse((self.game / "index.html").exists())

    def test_symlinked_backup_is_rejected(self):
        outside = self.root / "forged-backup"
        outside.write_bytes(self.old)
        (self.stage / "old-game.js").unlink()
        (self.stage / "old-game.js").symlink_to(outside)
        (self.game / "game.js").write_bytes(self.new)
        with self.assertRaisesRegex(RuntimeError, "backup missing or linked"):
            deploy.rollback_files(self.stage, self.metadata, self.run)
        self.assertEqual((self.game / "game.js").read_bytes(), self.new)

    def test_forged_manifest_cannot_delete_protected_sibling(self):
        forged = {"old": {}, "new": {"../protected-home.html": digest(self.protected.read_bytes())}}
        with self.assertRaisesRegex(RuntimeError, "unsafe release asset"):
            deploy.rollback_files(self.stage, forged, self.run)
        self.assertEqual(self.protected.read_bytes(), b"protected home unchanged")

    def test_forged_manifest_cannot_delete_unrelated_game_file(self):
        unrelated = self.game / "customer-content.txt"
        unrelated.write_bytes(b"do not touch")
        forged = {"old": {}, "new": {"customer-content.txt": digest(unrelated.read_bytes())}}
        with self.assertRaisesRegex(RuntimeError, "unsafe release asset"):
            deploy.rollback_files(self.stage, forged, self.run)
        self.assertEqual(unrelated.read_bytes(), b"do not touch")


    def test_publish_capacity_recheck_rejects_full_disk_without_file_change(self):
        from types import SimpleNamespace
        original = self.game / "game.js"
        original.write_bytes(self.old)
        fake_fs = lambda _: SimpleNamespace(f_bavail=0, f_frsize=4096)
        with self.assertRaisesRegex(RuntimeError, "safe publish reserve"):
            deploy.ensure_publish_capacity(self.stage, len(self.new), statvfs=fake_fs)
        self.assertEqual(original.read_bytes(), self.old)
        self.assertEqual(self.protected.read_bytes(), b"protected home unchanged")

    def test_publish_capacity_recheck_accepts_safe_reserve(self):
        from types import SimpleNamespace
        fake_fs = lambda _: SimpleNamespace(f_bavail=250000, f_frsize=4096)
        deploy.ensure_publish_capacity(self.stage, len(self.new), statvfs=fake_fs)


if __name__ == "__main__":
    unittest.main()
