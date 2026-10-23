"""Standalone safe resource publisher regression checks."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("adapter", ROOT / "scripts/factory_public_library_adapter.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ResourceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.mpw = self.home / "mojplaywin.com"
        self.zm = self.home / "public_html"
        for root in (self.mpw, self.zm, self.zm / "tala"):
            root.mkdir(parents=True, exist_ok=True)
            (root / "index.html").write_text("original")
        release = self.mpw / "factory-releases" / mod.RELEASE
        release.mkdir(parents=True)
        with zipfile.ZipFile(release / mod.ZIP, "w") as archive:
            archive.writestr("farm_enterprise_economics/calculator.py", "print(1)")
            archive.writestr("farm_enterprise_economics/README.md", "Example only")
        self.hash = hashlib.sha256((release / mod.ZIP).read_bytes()).hexdigest()
        (release / "SHA256SUMS.txt").write_text(self.hash + "  " + mod.ZIP + "\n")
        (release / "index.html").write_text("Farm Enterprise Economics Toolkit " + self.hash)

    def test_fanout_is_additive_and_sale_free(self):
        for site_id, (root_name, _, _) in mod.ALLOWED.items():
            result = mod.publish(self.home, site_id)
            self.assertEqual(result["products"], 1)
            root = self.home / root_name
            self.assertEqual((root / "index.html").read_text(), "original")
            location = ("factory-releases/resources" if site_id == "mojplaywin-main" else "factory-products")
            record = json.loads((root / location / "catalog.json").read_text())
            self.assertEqual(record["products"][0]["sha256"], self.hash)
            self.assertFalse(record["purchase_required"])
            self.assertIn(mod.CANONICAL, (root / location / "index.html").read_text())
            self.assertIn("PassengerEnabled off", (root / location / ".htaccess").read_text())
        mod.publish(self.home, "zomorod-main")

    def test_restricted_umask_and_existing_private_directory_are_fixed(self):
        # Previously the published files existed but parent folders stayed
        # 0700 (the job's umask 077), causing live HTTP 404/403.
        old = os.umask(0o077)
        try:
            mod.publish(self.home, "mojplaywin-main")
            dest = self.mpw / "factory-releases" / "resources"
            self.assertEqual(dest.stat().st_mode & 0o777, 0o755)
            dest.chmod(0o700)
            mod.publish(self.home, "mojplaywin-main")
            self.assertEqual(dest.stat().st_mode & 0o777, 0o755)
            self.assertEqual((dest / "catalog.json").stat().st_mode & 0o777, 0o644)
            self.assertEqual((dest / mod.MARKER).stat().st_mode & 0o777, 0o600)
        finally:
            os.umask(old)

    def test_existing_non_factory_directory_is_protected(self):
        target = self.mpw / "factory-releases" / "resources"
        target.mkdir()
        (target / "custom.html").write_text("preserve")
        with self.assertRaisesRegex(RuntimeError, "EXISTING_NON_FACTORY_DIRECTORY"):
            mod.publish(self.home, "mojplaywin-main")
        self.assertEqual((target / "custom.html").read_text(), "preserve")

    def test_invalid_checksum_blocks_publication(self):
        checksum = self.mpw / "factory-releases" / mod.RELEASE / "SHA256SUMS.txt"
        checksum.write_text("0" * 64 + "  " + mod.ZIP)
        with self.assertRaisesRegex(RuntimeError, "HASH_NOT_VALID"):
            mod.publish(self.home, "zomorod-main")
        self.assertFalse((self.zm / "factory-products").exists())

    def test_unknown_subsite_never_altered(self):
        with self.assertRaisesRegex(ValueError, "SITE_NOT_ALLOWED"):
            mod.publish(self.home, "mojplaywin-farnaz")
        self.assertFalse((self.mpw / "farnaz").exists())
