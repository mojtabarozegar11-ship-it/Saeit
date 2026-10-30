"""S-01 -> G-01 offline release handoff: synthetic fixtures only."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.s01_g01_release_package_offline_20261030 import build

ASSETS = ["index.html", "game.js", "game.css", "tactical-map.mjs",
          "objective-navigation.mjs", "campaign-backup.mjs",
          "THREE-LICENSE.txt", "ASSET-CREDITS.md"]


class OfflineReleasePackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.game = root / "game"
        self.game.mkdir()
        self.private = root / "private"
        self.private.mkdir(mode=0o700)
        self.output = self.private / "ramadan-candidate.zip"
        (self.game / "deploy.py").write_text(
            "ASSETS = " + repr(ASSETS) + "\n", encoding="utf-8")
        data = {
            "index.html": b'<html><link rel="stylesheet" href="./game.css"><script src="./game.js"></script></html>',
            "game.css": b"body{display:block}",
            "game.js": (b"import './tactical-map.mjs';"
                        b"import './objective-navigation.mjs';"
                        b"import './campaign-backup.mjs';"),
            "tactical-map.mjs": b"export function relativeDirection() { return 0; }",
            "objective-navigation.mjs": b"export function objectiveWaypoint() { return 0; }",
            "campaign-backup.mjs": b"export function makeCampaignBackup() { return 0; }",
            "THREE-LICENSE.txt": b"The MIT License - synthetic fixture",
            "ASSET-CREDITS.md": b"CC BY 4.0 synthetic fixture",
            ".htaccess": b"PassengerEnabled off\nDirectoryIndex index.html\n",
        }
        for name, body in data.items():
            (self.game / name).write_bytes(body)

    def test_private_zip_readback_manifest_and_no_release_claim(self):
        result = build(self.game, self.output)
        self.assertEqual(result["asset_count"], 9)
        self.assertFalse(result["deployment_authorized"])
        self.assertFalse(result["commercial_rights_verified"])
        self.assertTrue(self.output.is_file())
        with zipfile.ZipFile(self.output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(result["assets_sha256"]["game.js"],
                             hashlib.sha256(archive.read("game.js")).hexdigest())

    def test_existing_output_is_not_overwritten(self):
        self.output.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            build(self.game, self.output)
        self.assertEqual(self.output.read_bytes(), b"existing")

    def test_symlinked_asset_is_refused(self):
        target = self.game / "real.mjs"
        target.write_bytes(b"relativeDirection")
        (self.game / "tactical-map.mjs").unlink()
        (self.game / "tactical-map.mjs").symlink_to(target)
        with self.assertRaises(OSError):
            build(self.game, self.output)
        self.assertFalse(self.output.exists())

    def test_missing_objective_module_is_refused_before_zip_creation(self):
        self.game.joinpath("deploy.py").write_text(
            "ASSETS = " + repr([a for a in ASSETS if a != "objective-navigation.mjs"]) + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            build(self.game, self.output)
        self.assertFalse(self.output.exists())

    def test_unreferenced_campaign_module_is_refused(self):
        self.game.joinpath("game.js").write_bytes(
            b"import './tactical-map.mjs'; import './objective-navigation.mjs';"
        )
        with self.assertRaises(ValueError):
            build(self.game, self.output)
        self.assertFalse(self.output.exists())

    def test_remote_script_refused_before_archive(self):
        self.game.joinpath("index.html").write_bytes(
            b'<link rel="stylesheet" href="./game.css"><script src="https://other.example/app.js"></script>'
        )
        with self.assertRaises(ValueError):
            build(self.game, self.output)
        self.assertFalse(self.output.exists())

    def test_missing_local_image_refused_before_archive(self):
        self.game.joinpath("index.html").write_bytes(
            b'<link rel="stylesheet" href="./game.css"><script src="./game.js"></script>'
            b'<img src="./unlisted.webp">'
        )
        with self.assertRaises(ValueError):
            build(self.game, self.output)
        self.assertFalse(self.output.exists())

    def test_html_base_url_refused_before_archive(self):
        self.game.joinpath("index.html").write_bytes(
            b'<base href="https://other.example/"><link rel="stylesheet" href="./game.css">'
            b'<script src="./game.js"></script>'
        )
        with self.assertRaises(ValueError):
            build(self.game, self.output)
        self.assertFalse(self.output.exists())

    def test_public_destination_is_refused(self):
        public = Path(self.tmp.name) / "public"
        public.mkdir(mode=0o755)
        with self.assertRaises(ValueError):
            build(self.game, public / "candidate.zip")
        self.assertFalse((public / "candidate.zip").exists())


if __name__ == "__main__":
    unittest.main()
