"""Offline regression checks for bounded image-only static manifest repair."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.mpw_header_static_manifest_repair import (
    ASSET, CSS, apply, audit, git_blob_sha, hashed_name, manifest_for_asset,
    rollback,
)


class HeaderManifestRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.app = root / "app"
        (self.app / "core/static/site").mkdir(parents=True)
        self.static = self.app / "staticfiles"
        (self.static / "site").mkdir(parents=True)
        (self.static / "site/mojplaywin.123abc456def.css").write_text("body{}", encoding="utf-8")
        self.manifest = self.static / "staticfiles.json"
        self.manifest.write_text(json.dumps({
            "version": "1.1", "hash": "original", "paths": {CSS: "site/mojplaywin.123abc456def.css"},
        }), encoding="utf-8")
        self.stage = root / "stage"
        self.stage.mkdir()
        self.jpeg = self.stage / "mojplaywin-header-emblem.jpg"
        self.raw = b"\xff\xd8" + bytes(range(256)) * 6 + b"\xff\xd9"
        self.jpeg.write_bytes(self.raw)
        self.blob = git_blob_sha(self.raw)
        self.backup_parent = root / "backups"
        self.backup_parent.mkdir()
        self.backup = self.backup_parent / "101"

    def test_read_only_audit_reports_missing_asset_with_zero_writes(self):
        before = self.manifest.read_bytes()
        result = audit(self.app, self.jpeg, self.blob)
        self.assertEqual(result["status"], "repair_required")
        self.assertFalse(result["source_present"])
        self.assertFalse(result["collected_present"])
        self.assertFalse(result["hashed_present"])
        self.assertFalse(result["writes_performed"])
        self.assertEqual(self.manifest.read_bytes(), before)
        self.assertFalse(self.backup.exists())

    def test_apply_then_rollback_restores_exact_manifest_and_removes_only_created_files(self):
        before = self.manifest.read_bytes()
        result = apply(self.app, self.jpeg, self.backup, self.blob)
        self.assertEqual(result["status"], "applied")
        self.assertTrue(result["passenger_restart_required"])
        self.assertEqual((self.app / "core/static" / ASSET).read_bytes(), self.raw)
        self.assertEqual((self.static / ASSET).read_bytes(), self.raw)
        target = self.static / hashed_name(self.raw)
        self.assertEqual(target.read_bytes(), self.raw)
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["paths"][ASSET], hashed_name(self.raw))
        self.assertIn(CSS, manifest["paths"])
        self.assertEqual(apply(self.app, self.jpeg, self.backup_parent / "102", self.blob)["status"],
                         "already_ready")
        rolled = rollback(self.app, self.backup)
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(self.manifest.read_bytes(), before)
        self.assertFalse((self.app / "core/static" / ASSET).exists())
        self.assertFalse((self.static / ASSET).exists())
        self.assertFalse(target.exists())
        self.assertTrue((self.static / "site/mojplaywin.123abc456def.css").is_file())

    def test_invalid_staged_image_refused_without_backup_or_write(self):
        original = self.manifest.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "pinned source identity"):
            apply(self.app, self.jpeg, self.backup, "0" * 40)
        self.assertFalse(self.backup.exists())
        self.assertEqual(self.manifest.read_bytes(), original)

    def test_foreign_collected_header_is_never_overwritten(self):
        (self.static / ASSET).write_bytes(b"different")
        with self.assertRaisesRegex(RuntimeError, "different image"):
            apply(self.app, self.jpeg, self.backup, self.blob)
        self.assertFalse(self.backup.exists())

    def test_manifest_collision_is_fail_closed(self):
        self.manifest.write_text(json.dumps({
            "version": "1.1", "paths": {CSS: "site/mojplaywin.123abc456def.css",
                                         ASSET: "site/mojplaywin-header-emblem.old.jpg"},
        }), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "different existing manifest target"):
            apply(self.app, self.jpeg, self.backup, self.blob)

    def test_manifest_target_is_django_style_and_unrelated_mapping_is_preserved(self):
        existing = json.dumps({"version": "1.1", "paths": {CSS: "site/mojplaywin.123abc456def.css",
                                                         "something/else.png": "something/else.f00.png"}}).encode()
        name, manifest = manifest_for_asset(existing, self.raw)
        self.assertEqual(name, hashed_name(self.raw))
        found = json.loads(manifest)
        self.assertEqual(found["paths"]["something/else.png"], "something/else.f00.png")
        self.assertEqual(len(found["hash"]), 12)

    def test_rollback_refuses_concurrent_change_without_touching_files(self):
        apply(self.app, self.jpeg, self.backup, self.blob)
        target = self.static / hashed_name(self.raw)
        target.write_bytes(b"changed after apply")
        before = self.manifest.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "concurrent change"):
            rollback(self.app, self.backup)
        self.assertEqual(self.manifest.read_bytes(), before)
        self.assertEqual(target.read_bytes(), b"changed after apply")

    def test_symlink_collected_file_is_refused(self):
        (self.static / ASSET).symlink_to(self.jpeg)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            apply(self.app, self.jpeg, self.backup, self.blob)
        self.assertFalse(self.backup.exists())

    def test_interrupted_prepared_install_can_be_rolled_back(self):
        old_manifest = self.manifest.read_bytes()
        apply(self.app, self.jpeg, self.backup, self.blob)
        record_path = self.backup / "record.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["status"] = "prepared"
        record_path.write_text(json.dumps(record), encoding="utf-8")
        (self.app / "core/static" / ASSET).unlink()
        self.assertEqual(rollback(self.app, self.backup)["status"], "rolled_back")
        self.assertEqual(self.manifest.read_bytes(), old_manifest)
        self.assertFalse((self.static / ASSET).exists())
        self.assertFalse((self.static / hashed_name(self.raw)).exists())

    def test_missing_css_collected_target_fails_closed(self):
        (self.static / "site/mojplaywin.123abc456def.css").unlink()
        with self.assertRaisesRegex(RuntimeError, "Required file missing"):
            apply(self.app, self.jpeg, self.backup, self.blob)
        self.assertFalse(self.backup.exists())


if __name__ == "__main__":
    unittest.main()
