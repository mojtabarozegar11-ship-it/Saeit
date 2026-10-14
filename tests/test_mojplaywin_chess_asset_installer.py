"""Pure-Python checks for MojPlayWin ZIP verification and fail-closed installation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SRC = Path(__file__).resolve().parents[1] / "scripts" / "mojplaywin_chess_assets.py"
spec = importlib.util.spec_from_file_location("moj_chess_assets", SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ChessAssetTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original_files = mod.FILES
        self.original_home = mod.HOME
        self.addCleanup(setattr, mod, "FILES", self.original_files)
        self.addCleanup(setattr, mod, "HOME", self.original_home)
        mod.HOME = self.root
        self.zip_path = self.root / "assets.zip"
        self.target = self.root / "MojPlayWin_Private_Assets" / "chess-improvement-2026"
        self.assets = {
            "MojPlayWin_Science_and_Practice_of_Chess_Improvement.pdf": b"%PDF-1.7\nverified ebook\n",
            "MojPlayWin_Chess_Improvement_Poster_English_50_Off.png": b"\x89PNG\r\n\x1a\nposter",
            "MojPlayWin_Chess_Improvement_English_Sales_Copy.md": b"# Sales copy\n",
            "MojPlayWin_Chess_Improvement_Asset_Manifest.json": json.dumps(
                {"id": mod.PRODUCT_ID, "product_id_in_live_database": 72}
            ).encode(),
        }
        mod.FILES = {name: (len(blob), hashlib.sha256(blob).hexdigest())
                     for name, blob in self.assets.items()}
        self.write_zip(self.assets)

    def write_zip(self, assets):
        with zipfile.ZipFile(self.zip_path, "w") as z:
            for name, blob in assets.items():
                z.writestr(name, blob)

    def test_private_install_verifies_every_byte_and_is_idempotent(self):
        self.assertEqual(len(mod.inspect_zip(self.zip_path)), 4)
        mod.install_assets(self.zip_path, self.target)
        self.assertTrue(mod.verify_installed(self.target))
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)
        for name in mod.FILES:
            self.assertEqual((self.target / name).stat().st_mode & 0o777, 0o600)
        mod.install_assets(self.zip_path, self.target)
        self.assertTrue(mod.verify_installed(self.target))

    def test_rejects_tampered_book(self):
        bad = dict(self.assets)
        bad["MojPlayWin_Science_and_Practice_of_Chess_Improvement.pdf"] += b"bad"
        self.write_zip(bad)
        with self.assertRaises(ValueError):
            mod.inspect_zip(self.zip_path)
        self.assertFalse(self.target.exists())

    def test_rejects_extra_paths(self):
        bad = dict(self.assets)
        bad["../outside.txt"] = b"bad"
        self.write_zip(bad)
        with self.assertRaises(ValueError):
            mod.inspect_zip(self.zip_path)
        self.assertFalse(self.target.exists())

    def test_rejects_wrong_manifest_identity(self):
        bad = dict(self.assets)
        bad["MojPlayWin_Chess_Improvement_Asset_Manifest.json"] = b'{"id":"other","product_id_in_live_database":72}'
        mod.FILES = {k: (len(v), hashlib.sha256(v).hexdigest()) for k, v in bad.items()}
        self.write_zip(bad)
        with self.assertRaises(ValueError):
            mod.inspect_zip(self.zip_path)

if __name__ == "__main__":
    unittest.main()
