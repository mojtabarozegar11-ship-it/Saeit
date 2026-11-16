"""Strict, offline archive-integrity and all-or-nothing restore checks.

This does NOT touch any real site, database, wallet or customer record.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import deploy_mojplaywin_moj_prop_backend as backend


RUN = "840001"
SHA = "a" * 40
FILES = (Path("core/a.py"), Path("core/b.py"))


class MojPropBackupIntegrityTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.base = Path(root.name)
        self.live = self.base / "live"
        self.live.mkdir()
        self.backup = self.base / RUN
        self.backup.mkdir(mode=0o700)
        self.backup.chmod(0o700)
        self.patch1 = patch.object(backend, "ROOT", self.live)
        self.patch2 = patch.object(backend, "ALL_FILES", FILES)
        self.patch3 = patch.object(backend, "restart_passenger")
        self.patch1.start()
        self.patch2.start()
        self.restart = self.patch3.start()
        self.addCleanup(self.patch3.stop)
        self.addCleanup(self.patch2.stop)
        self.addCleanup(self.patch1.stop)
        self.records = {str(relative): b"original-" + str(i).encode()
                        for i, relative in enumerate(FILES)}
        for relative in FILES:
            destination = self.live / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(self.records[str(relative)])
        self.build_backup()

    def build_backup(self):
        manifest = {"run_id": RUN, "commit": SHA, "files": list(map(str, FILES))}
        for rel in FILES:
            backend.backup_target(self.live / rel, self.backup, manifest, rel)
        (self.backup / "manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(backend.verify_backup_manifest(self.backup), manifest)

    def rewrite_manifest(self, update):
        p = self.backup / "manifest.json"
        manifest = json.loads(p.read_text())
        update(manifest)
        p.write_text(json.dumps(manifest))

    def test_complete_verified_backup_restores_exact_original_bytes(self):
        for rel in FILES:
            (self.live / rel).write_bytes(b"new-content")
        with contextlib.redirect_stdout(io.StringIO()):
            backend.restore(self.backup)
        for rel in FILES:
            self.assertEqual((self.live / rel).read_bytes(), self.records[str(rel)])
        self.restart.assert_called_once()

    def test_corrupt_second_backup_refuses_all_restore_without_partial_writes(self):
        (self.backup / FILES[1]).write_bytes(b"tampered")
        for rel in FILES:
            (self.live / rel).write_bytes(b"deployed-version")
        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            backend.restore(self.backup)
        for rel in FILES:
            self.assertEqual((self.live / rel).read_bytes(), b"deployed-version")
        self.restart.assert_not_called()

    def test_missing_second_backup_refuses_all_restore_without_partial_writes(self):
        (self.backup / FILES[1]).unlink()
        for rel in FILES:
            (self.live / rel).write_bytes(b"deployed-version")
        with self.assertRaisesRegex(RuntimeError, "missing or unsafe"):
            backend.restore(self.backup)
        self.assertEqual((self.live / FILES[0]).read_bytes(), b"deployed-version")
        self.restart.assert_not_called()

    def test_wrong_inventory_and_duplicate_path_are_rejected(self):
        self.rewrite_manifest(lambda v: v["files"].append(str(FILES[0])))
        with self.assertRaisesRegex(RuntimeError, "inventory differs"):
            backend.verify_backup_manifest(self.backup)

    def test_wrong_run_id_cannot_replay_another_backup(self):
        self.rewrite_manifest(lambda v: v.update(run_id="840099"))
        with self.assertRaisesRegex(RuntimeError, "does not match directory"):
            backend.verify_backup_manifest(self.backup)

    def test_wrong_commit_and_missing_digest_are_rejected(self):
        self.rewrite_manifest(lambda v: v.update(commit="invalid"))
        with self.assertRaises(ValueError):
            backend.verify_backup_manifest(self.backup)
        self.rewrite_manifest(lambda v: v.update(commit=SHA))
        self.rewrite_manifest(lambda v: v[str(FILES[0])].pop("sha256"))
        with self.assertRaisesRegex(RuntimeError, "digest is malformed"):
            backend.verify_backup_manifest(self.backup)

    def test_symlink_backup_source_is_rejected(self):
        original = self.backup / FILES[0]
        original.unlink()
        original.symlink_to(self.live / FILES[0])
        with self.assertRaisesRegex(RuntimeError, "missing or unsafe"):
            backend.verify_backup_manifest(self.backup)

    def test_symlinked_backup_parent_is_refused_before_restoration(self):
        core = self.backup / "core"
        relocated = self.base / "relocated-core"
        core.rename(relocated)
        core.symlink_to(relocated, target_is_directory=True)
        for rel in FILES:
            (self.live / rel).write_bytes(b"new-live-bytes")
        with self.assertRaisesRegex(RuntimeError, "symlink parent refused"):
            backend.restore(self.backup)
        for rel in FILES:
            self.assertEqual((self.live / rel).read_bytes(), b"new-live-bytes")
        self.restart.assert_not_called()

    def test_parent_guard_rejects_lexical_escape_outside_reviewed_tenant(self):
        escaped = self.live / ".." / "other-tenant" / "source.py"
        with self.assertRaisesRegex(RuntimeError, "traversal refused"):
            backend.assert_safe_parent(escaped, self.live)
        with self.assertRaisesRegex(RuntimeError, "escapes reviewed root"):
            backend.assert_safe_parent(self.base / "outside.py", self.live)

    def test_atomic_text_write_rejects_new_symlink_before_migration_write(self):
        source = self.base / "owner-source.py"
        source.write_text("# owner-owned, must remain\n", encoding="utf-8")
        target = self.live / "core" / "0041_new.py"
        target.symlink_to(source)
        with self.assertRaisesRegex(RuntimeError, "unsafe live target symlink"):
            backend.atomic_write_text(target, "print('new')\n", 0o640)
        self.assertTrue(target.is_symlink())
        self.assertEqual(source.read_text(encoding="utf-8"),
                         "# owner-owned, must remain\n")

    def test_atomic_replace_rejects_racing_live_symlink_without_changes(self):
        rel = FILES[0]
        target = self.live / rel
        external = self.base / "external-owner-file.txt"
        external.write_bytes(b"owner-unchanged")
        target.unlink()
        target.symlink_to(external)
        staged = self.base / "safe-staged.txt"
        staged.write_bytes(b"new-code")
        with self.assertRaisesRegex(RuntimeError, "unsafe live target symlink"):
            backend.atomic_replace(staged, target, 0o640)
        self.assertTrue(target.is_symlink())
        self.assertEqual(external.read_bytes(), b"owner-unchanged")
        self.assertEqual(staged.read_bytes(), b"new-code")

    def test_oversized_backup_manifest_refused_before_parse_or_restore(self):
        manifest = self.backup / "manifest.json"
        manifest.write_bytes(b" " * (1024 * 1024 + 1))
        with self.assertRaisesRegex(RuntimeError, "manifest size is unsafe"):
            backend.verify_backup_manifest(self.backup)
        self.restart.assert_not_called()

    def test_empty_backup_manifest_refused_before_parse_or_restore(self):
        (self.backup / "manifest.json").write_bytes(b"")
        with self.assertRaisesRegex(RuntimeError, "manifest size is unsafe"):
            backend.verify_backup_manifest(self.backup)
        self.restart.assert_not_called()

    def test_group_writable_backend_backup_root_prevents_recovery(self):
        self.base.chmod(0o770)
        with self.assertRaisesRegex(RuntimeError, "private backend backup directory required"):
            backend.verify_backup_manifest(self.backup)
        self.base.chmod(0o700)

    def test_world_readable_backend_backup_dir_prevents_recovery(self):
        self.backup.chmod(0o705)
        with self.assertRaisesRegex(RuntimeError, "private backend backup directory required"):
            backend.verify_backup_manifest(self.backup)
        self.backup.chmod(0o700)

    def test_backup_run_symlink_parent_prevents_recovery(self):
        alias = self.base / "backup-alias"
        actual = self.base / "actual-backups"
        actual.mkdir(mode=0o700)
        actual.chmod(0o700)
        alias.symlink_to(actual, target_is_directory=True)
        inner = actual / "inner"
        inner.mkdir(mode=0o700)
        inner.chmod(0o700)
        run = inner / RUN
        run.mkdir(mode=0o700)
        run.chmod(0o700)
        with self.assertRaisesRegex(RuntimeError, "symlink ancestor"):
            backend.verify_backup_manifest(alias / "inner" / RUN)

    def test_backup_refuses_dangling_live_symlink_before_manifest_creation(self):
        rel = FILES[0]
        target = self.live / rel
        target.unlink()
        target.symlink_to(self.base / "unrelated-missing-owner-file")
        manifest = {"run_id": RUN, "commit": SHA, "files": list(map(str, FILES))}
        with self.assertRaisesRegex(RuntimeError, "unsafe live target symlink"):
            backend.backup_target(target, self.backup, manifest, rel)
        self.assertNotIn(str(rel), manifest)
        self.assertTrue(target.is_symlink())

    def test_backup_creation_rejects_symlinked_parent(self):
        core = self.backup / "core"
        relocated = self.base / "elsewhere"
        core.rename(relocated)
        core.symlink_to(relocated, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlink parent refused"):
            backend.backup_target(
                self.live / FILES[0], self.backup,
                {"run_id": RUN, "commit": SHA, "files": list(map(str, FILES))},
                FILES[0],
            )

    def test_post_preflight_source_mutation_detected_before_first_restore(self):
        original = backend.verify_backup_manifest
        def malicious_change_after_validation(backup):
            result = original(backup)
            (backup / FILES[0]).write_bytes(b"changed-since-preflight")
            return result
        for rel in FILES:
            (self.live / rel).write_bytes(b"active-production-version")
        with patch.object(backend, "verify_backup_manifest",
                          side_effect=malicious_change_after_validation):
            with self.assertRaisesRegex(RuntimeError, "changed during restore"):
                backend.restore(self.backup)
        for rel in FILES:
            self.assertEqual(
                (self.live / rel).read_bytes(), b"active-production-version"
            )
        self.restart.assert_not_called()

    def test_corrupt_restore_write_refused_without_restart(self):
        for rel in FILES:
            (self.live / rel).write_bytes(b"new-live-bytes")
        def damaged_copy(_source, target, _mode):
            target.write_bytes(b"corrupt-after-copy")
        with patch.object(backend, "atomic_replace", side_effect=damaged_copy):
            with self.assertRaisesRegex(RuntimeError, "failed verification"):
                backend.restore(self.backup)
        self.restart.assert_not_called()

    def test_broken_symlink_live_target_cannot_evade_absent_backup_check(self):
        rel = FILES[0]
        (self.backup / rel).unlink()
        self.rewrite_manifest(lambda m: m[str(rel)].update(
            existed=False,
        ))
        live = self.live / rel
        live.unlink()
        live.symlink_to(self.base / "nonexistent-future-target")
        with self.assertRaisesRegex(RuntimeError, "missing or unsafe"):
            backend.restore(self.backup)
        self.assertTrue(live.is_symlink())
        self.restart.assert_not_called()

    def test_unexpected_source_for_previously_absent_file_is_rejected(self):
        self.rewrite_manifest(lambda v: v[str(FILES[0])].update(existed=False))
        with self.assertRaisesRegex(RuntimeError, "unexpected source"):
            backend.verify_backup_manifest(self.backup)

    def test_invalid_mode_is_rejected(self):
        self.rewrite_manifest(lambda v: v[str(FILES[0])].update(mode=0o7777))
        with self.assertRaisesRegex(RuntimeError, "mode is invalid"):
            backend.verify_backup_manifest(self.backup)


if __name__ == "__main__":
    unittest.main()
