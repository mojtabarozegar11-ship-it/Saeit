"""Isolated regression checks: never connects to cPanel or opens customer data."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import mpw_staging_header_manifest_repair_20261107 as repair


class SingleAssetManifestTests(unittest.TestCase):
    def setUp(self):
        self.old = {
            "paths": {
                "site/mojplaywin.css": "site/mojplaywin.123456789abc.css",
                "site/a.png": "site/a.abcdefghijkl.png",
            },
            "version": "1.1",
            "hash": "oldhash",
        }
        self.raw = json.dumps(self.old).encode()
        self.image = b"jpeg synthetic fake bytes"

    def test_appends_only_one_asset_to_existing_manifest(self):
        result = json.loads(repair.update_manifest(self.raw, self.image))
        self.assertEqual(len(result["paths"]), 3)
        self.assertEqual(result["paths"]["site/a.png"], "site/a.abcdefghijkl.png")
        self.assertEqual(result["paths"]["site/mojplaywin.css"], "site/mojplaywin.123456789abc.css")
        self.assertEqual(result["paths"][repair.ASSET_NAME], repair.image_hashed_name(self.image))
        self.assertEqual(result["hash"], hashlib.md5(json.dumps(sorted(result["paths"].items())).encode()).hexdigest()[:12])

    def test_refuses_overwrite_of_existing_manifest_key(self):
        self.old["paths"][repair.ASSET_NAME] = "site/existing.jpg"
        with self.assertRaisesRegex(RuntimeError, "ENTRY_DRIFT"):
            repair.update_manifest(json.dumps(self.old).encode(), self.image)

    def test_refuses_bad_manifest_shape(self):
        for data in (b"[]", b'{"version": "2", "paths": {}}',
                     b'{"version": "1.1", "paths": {"site/mojplaywin.css": 4}}'):
            with self.assertRaises(RuntimeError):
                repair.update_manifest(data, self.image)

    def test_github_blob_pin_and_file_hash_differ(self):
        expected = hashlib.sha1(b"blob " + str(len(self.image)).encode() + b"\0" + self.image).hexdigest()
        self.assertEqual(repair.git_blob_id(self.image), expected)
        self.assertEqual(len(repair.image_hashed_name(self.image).split(".")[-2]), 12)

    def test_rollback_restores_manifest_and_removes_only_own_files(self):
        with tempfile.TemporaryDirectory() as root:
            app = Path(root) / "app"
            site = app / "core/static/site"
            collected = app / "staticfiles/site"
            site.mkdir(parents=True)
            collected.mkdir(parents=True)
            manifest = app / "staticfiles/staticfiles.json"
            manifest.write_bytes(self.raw)
            updated = repair.update_manifest(self.raw, self.image)
            hashed = app / "staticfiles" / repair.image_hashed_name(self.image)
            source = site / "mojplaywin-header-emblem.jpg"
            regular = collected / "mojplaywin-header-emblem.jpg"
            backup_root = Path(root) / "backups"
            backup = backup_root / "12345678"
            backup.mkdir(parents=True)
            (backup / "original-staticfiles.json").write_bytes(self.raw)
            (backup / "journal.json").write_text(json.dumps({
                "original_sha256": repair.sha256(self.raw),
                "updated_sha256": repair.sha256(updated),
                "image_sha256": repair.sha256(self.image),
                "hashed_name": repair.image_hashed_name(self.image),
                "manifest_mode": 0o644,
            }))
            for path in (source, regular, hashed):
                path.write_bytes(self.image)
            unrelated = collected / "something-else.css"
            unrelated.write_text("untouched")
            manifest.write_bytes(updated)
            with patch.multiple(repair, HOME=Path(root), APP=app, MANIFEST=manifest, SOURCE=source,
                                COLLECTED=regular, BACKUP_ROOT=backup_root):
                repair.rollback_journal("12345678")
            self.assertEqual(manifest.read_bytes(), self.raw)
            self.assertFalse(source.exists())
            self.assertFalse(regular.exists())
            self.assertFalse(hashed.exists())
            self.assertEqual(unrelated.read_text(), "untouched")

    def test_rollback_refuses_concurrent_manifest_changes(self):
        with tempfile.TemporaryDirectory() as root:
            app = Path(root) / "app"
            (app / "staticfiles").mkdir(parents=True)
            (app / "staticfiles/site").mkdir()
            manifest = app / "staticfiles/staticfiles.json"
            manifest.write_bytes(b"modified by another deploy")
            backup_root = Path(root) / "backups"
            backup = backup_root / "12345678"
            backup.mkdir(parents=True)
            (backup / "original-staticfiles.json").write_bytes(self.raw)
            (backup / "journal.json").write_text(json.dumps({
                "original_sha256": repair.sha256(self.raw),
                "updated_sha256": repair.sha256(repair.update_manifest(self.raw, self.image)),
                "image_sha256": repair.sha256(self.image),
                "hashed_name": repair.image_hashed_name(self.image),
                "manifest_mode": 0o644,
            }))
            with patch.multiple(repair, HOME=Path(root), APP=app, MANIFEST=manifest,
                                COLLECTED=app / "staticfiles/site/mojplaywin-header-emblem.jpg",
                                BACKUP_ROOT=backup_root):
                with self.assertRaisesRegex(RuntimeError, "CONCURRENT_MANIFEST"):
                    repair.rollback_journal("12345678")
            self.assertEqual(manifest.read_bytes(), b"modified by another deploy")


if __name__ == "__main__":
    unittest.main()
