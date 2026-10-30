"""S-01 -> G-01 offline release handoff: synthetic fixtures only."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.s01_g01_release_package_offline_20261030 import build

ASSETS = ["index.html", "game.js", "tactical-map.mjs",
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
            "index.html": b"<html>synthetic only</html>",
            "game.js": b"import './tactical-map.mjs';",
            "tactical-map.mjs": b"export function relativeDirection() { return 0; }",
            "THREE-LICENSE.txt": b"The MIT License - synthetic fixture",
            "ASSET-CREDITS.md": b"CC BY 4.0 synthetic fixture",
            ".htaccess": b"PassengerEnabled off\nDirectoryIndex index.html\n",
        }
        for name, body in data.items():
            (self.game / name).write_bytes(body)

    def test_private_zip_readback_manifest_and_no_release_claim(self):
        result = build(self.game, self.output)
        self.assertEqual(result["asset_count"], 6)
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

    def test_public_destination_is_refused(self):
        public = Path(self.tmp.name) / "public"
        public.mkdir(mode=0o755)
        with self.assertRaises(ValueError):
            build(self.game, public / "candidate.zip")
        self.assertFalse((public / "candidate.zip").exists())


if __name__ == "__main__":
    unittest.main()
