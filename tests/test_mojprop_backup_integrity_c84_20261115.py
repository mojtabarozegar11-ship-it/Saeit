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
        self.backup.mkdir()
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
