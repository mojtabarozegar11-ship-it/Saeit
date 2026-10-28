#!/usr/bin/env python3
"""No-network regression for the standalone Ramadan War preview artifact."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from build_preview import build_preview


class PreviewArchiveTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.root = self.base / "game"
        (self.root / "three-addons").mkdir(parents=True)
        (self.root / "index.html").write_text("<!doctype html><script src='game.js'></script>")
        (self.root / "game.js").write_bytes(b"playable game logic")
        (self.root / "three-addons/loader.js").write_bytes(b"loader")
        self.assets = ["index.html", "game.js", "three-addons/loader.js"]
        self.out = self.base / "preview.zip"

    def build(self, assets=None, sizes=None):
        return build_preview(self.root, self.out, self.assets if assets is None else assets,
                             sizes)

    def test_package_contains_exact_runnable_assets_and_sha_manifest(self):
        result = self.build()
        self.assertEqual(result["asset_count"], 3)
        self.assertEqual(result["archive_sha256"],
                         hashlib.sha256(self.out.read_bytes()).hexdigest())
        with ZipFile(self.out) as archive:
            manifest = json.loads(archive.read("ramadan-war/preview-manifest.json"))
            self.assertEqual(manifest["payment_status"], "disabled")
            self.assertEqual(manifest["format"], "ramadan-war-offline-preview-v1")
            for rel in self.assets:
                data = (self.root / rel).read_bytes()
                self.assertEqual(archive.read("ramadan-war/" + rel), data)
                self.assertEqual(manifest["files"][rel]["sha256"],
                                 hashlib.sha256(data).hexdigest())
        first = self.out.read_bytes()
        self.build()
        self.assertEqual(self.out.read_bytes(), first, "preview must be reproducible")

    def test_rejects_incomplete_models_before_archive(self):
        with self.assertRaisesRegex(ValueError, "incomplete preview model"):
            self.build(sizes={"game.js": 999})
        self.assertFalse(self.out.exists())

    def test_rejects_missing_and_empty_assets(self):
        (self.root / "game.js").unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            self.build()
        (self.root / "game.js").write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "empty"):
            self.build()
        self.assertFalse(self.out.exists())

    def test_rejects_path_traversal_and_duplicate_manifest(self):
        for paths in ([], ["game.js", "game.js"], ["../customer.json"],
                      ["/etc/passwd"], ["./game.js"], ["three-addons//loader.js"]):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                self.build(assets=paths)
        self.assertFalse(self.out.exists())

    def test_rejects_symlinked_file_and_ancestor(self):
        outside = self.base / "customer"
        outside.write_bytes(b"private")
        (self.root / "game.js").unlink()
        (self.root / "game.js").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            self.build()
        (self.root / "game.js").unlink()
        (self.root / "game.js").write_bytes(b"ok")
        (self.root / "three-addons/loader.js").unlink()
        (self.root / "three-addons").rmdir()
        (self.root / "three-addons").symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            self.build()
        self.assertEqual(outside.read_bytes(), b"private")

    def test_refuses_output_inside_source(self):
        with self.assertRaisesRegex(ValueError, "outside game source"):
            build_preview(self.root, self.root / "preview.zip", self.assets)
        self.assertFalse((self.root / "preview.zip").exists())


if __name__ == "__main__":
    unittest.main()
