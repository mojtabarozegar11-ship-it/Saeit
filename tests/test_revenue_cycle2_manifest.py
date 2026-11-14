"""Reproducible public synthetic manifests, without customer paths."""
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from revenue_cycle2_manifest import ALLOWED_FILES, manifest


class ManifestTests(unittest.TestCase):
    def test_four_fixed_synthetic_assets(self):
        record = manifest()
        self.assertEqual(len(record["assets"]), 4)
        self.assertEqual({x["path"] for x in record["assets"]}, set(ALLOWED_FILES))

    def test_sha256_reconciles(self):
        record = manifest()
        for asset in record["assets"]:
            with self.subTest(path=asset["path"]):
                data = (ROOT / asset["path"]).read_bytes()
                self.assertEqual(asset["sha256"], hashlib.sha256(data).hexdigest())
                self.assertEqual(asset["bytes"], len(data))

    def test_no_customer_data_or_live_claim(self):
        record = manifest()
        self.assertTrue(record["synthetic_only"])
        self.assertFalse(record["customer_data_included"])
        self.assertFalse(record["verified_live_delivery"])


if __name__ == "__main__":
    unittest.main()
