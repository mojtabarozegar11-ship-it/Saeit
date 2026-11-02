"""Offline contract: the public ZM catalog never advertises altered free releases."""
import hashlib
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "content/zomorod-v11/store_index.php"
LIB = ROOT / "content/zomorod-v11/site_store.php"
URL = "/store/free-products/wheat-seed-rate-planner-v1/index.html"


@unittest.skipUnless(shutil.which("php"), "PHP CLI required")
class FreeCatalogIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.store = self.home / "public_html/store"
        self.store.mkdir(parents=True)
        self.private = self.home / ".private/zomorod-business"
        self.private.mkdir(parents=True)
        shutil.copyfile(INDEX, self.store / "index.php")
        shutil.copyfile(LIB, self.private / "site_store.php")
        self.product_dir = self.store / "free-products/wheat-seed-rate-planner-v1"
        self.product_dir.mkdir(parents=True)
        self.file = self.product_dir / "index.html"
        self.file.write_bytes(b"verified original free release")
        self.sha = hashlib.sha256(self.file.read_bytes()).hexdigest()
        self.dbpath = self.private / "site_store.sqlite3"
        with sqlite3.connect(self.dbpath) as db:
            db.execute("""CREATE TABLE free_digital_products (
                id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL, description TEXT NOT NULL,
                download_path TEXT NOT NULL UNIQUE,
                artifact_sha256 TEXT NOT NULL, license_text TEXT NOT NULL,
                price_irr INTEGER NOT NULL DEFAULT 0 CHECK(price_irr=0),
                enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN(0,1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("""INSERT INTO free_digital_products
                (sku,title,description,download_path,artifact_sha256,license_text,price_irr,enabled)
                VALUES(?,?,?,?,?,?,0,1)""",
                ("wheat_seed_rate_v1", "Verified free seed calculator",
                 "Offline free artifact", URL, self.sha, "Free educational use"))

    def tearDown(self):
        self.temp.cleanup()

    def render(self):
        run = subprocess.run(["php", str(self.store / "index.php")],
                             capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn("Warning:", run.stderr)
        return run.stdout

    def update(self, column, value):
        self.assertIn(column, ("artifact_sha256", "license_text", "enabled"))
        with sqlite3.connect(self.dbpath) as db:
            db.execute(f"UPDATE free_digital_products SET {column}=?", (value,))

    def test_valid_release_is_listed_as_free_without_checkout(self):
        html = self.render()
        self.assertIn('href="' + URL + '"', html)
        self.assertIn("رایگان — بدون پرداخت", html)
        self.assertIn("خرید آنلاین و برداشت وجه غیرفعال است", html)
        self.assertNotIn("<form", html.lower())

    def test_tampered_artifact_is_not_advertised(self):
        self.file.write_bytes(b"altered content after verified release")
        html = self.render()
        self.assertNotIn('href="' + URL + '"', html)
        self.assertNotIn("Verified free seed calculator", html)
        self.assertIn("کاتالوگ در حال تکمیل", html)

    def test_missing_artifact_is_not_advertised(self):
        self.file.unlink()
        self.assertNotIn('href="' + URL + '"', self.render())

    def test_symlinked_artifact_is_not_advertised(self):
        other = self.home / "external.html"
        other.write_bytes(self.file.read_bytes())
        self.file.unlink()
        self.file.symlink_to(other)
        self.assertNotIn('href="' + URL + '"', self.render())

    def test_symlinked_product_directory_is_not_advertised(self):
        other = self.home / "outside"
        self.product_dir.rename(other)
        self.product_dir.symlink_to(other, target_is_directory=True)
        self.assertNotIn('href="' + URL + '"', self.render())

    def test_blank_license_cannot_be_publicly_advertised(self):
        self.update("license_text", "   ")
        self.assertNotIn('href="' + URL + '"', self.render())

    def test_wrong_digest_cannot_be_publicly_advertised(self):
        self.update("artifact_sha256", "0" * 64)
        self.assertNotIn('href="' + URL + '"', self.render())

    def test_disabled_record_is_not_publicly_advertised(self):
        self.update("enabled", 0)
        self.assertNotIn('href="' + URL + '"', self.render())


if __name__ == "__main__":
    unittest.main()
