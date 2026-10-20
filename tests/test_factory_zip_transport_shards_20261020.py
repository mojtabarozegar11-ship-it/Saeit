"""Real byte-for-byte shard reassembly; no commercial release."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

PATH = Path(__file__).resolve().parents[1] / "scripts/factory_zip_transport_shards_20261020.py"
spec = importlib.util.spec_from_file_location("shards", PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class PrivateShards(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.recipe = m.RECIPES[0]
        folder = self.root / "digital-products" / self.recipe
        folder.mkdir(parents=True)
        self.folder = folder
        self.archive = folder / (self.recipe + "-internal-qa.zip")
        with zipfile.ZipFile(self.archive, "w") as z:
            for i in range(97):
                z.writestr(self.recipe + "/asset%03d.txt" % i, "file-%03d" % i)
        self.meta = folder / "manufacturing_manifest.json"
        self.meta.write_text(json.dumps({
            "recipe": self.recipe, "qa_status": "passed",
            "source_sha256": "a" * 64,
            "artifact_sha256": m.filehash(self.archive),
            "owner_publication_approval": False, "public_listing_enabled": False
        }))
    def test_complete_lossless_two_part_cycle(self):
        original = self.archive.read_bytes()
        first = m.cycle(self.root, (self.recipe,))
        self.assertEqual(first["products_verified"], 1)
        self.assertEqual(first["total_parts"], 2)
        self.assertEqual(first["all_source_members_restored"], 97)
        self.assertEqual(first["publications"], 0)
        self.assertEqual(original, self.archive.read_bytes())
        self.assertFalse(m.cycle(self.root, (self.recipe,))["products"][0]["created"])
        folder = self.root / "product-lifecycle/private-transport-shards" / self.recipe / m.filehash(self.archive)
        receipt = m.load(folder / "receipt.json")
        self.assertTrue(receipt["reconstruction_verified"])
        self.assertFalse(receipt["public_distribution_allowed"])
        self.assertFalse(receipt["owner_publication_approval"])
        self.assertTrue(all(p["members"] <= 80 for p in receipt["parts"]))
        self.assertEqual(len(receipt["files"]), 97)
    def test_reject_damaged_private_shard(self):
        m.cycle(self.root, (self.recipe,))
        folder = self.root / "product-lifecycle/private-transport-shards" / self.recipe / m.filehash(self.archive)
        (folder / "part-001.zip").write_bytes(b"bad bytes")
        with self.assertRaisesRegex(ValueError, "SHARD_PART_SHA_MISMATCH"):
            m.cycle(self.root, (self.recipe,))
    def test_reject_original_sha_tampering_and_no_approvals(self):
        data = json.loads(self.meta.read_text())
        data["artifact_sha256"] = "f" * 64
        self.meta.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "SHARD_SOURCE_MANIFEST_MISMATCH"):
            m.cycle(self.root, (self.recipe,))
        self.assertFalse((self.root / "product-lifecycle/private-transport-shards").exists())
    def test_unsafe_member_fails_closed(self):
        with zipfile.ZipFile(self.archive, "w") as z:
            for i in range(81):
                z.writestr(self.recipe + "/asset%03d.txt" % i, "item")
            z.writestr(self.recipe + "/../unsafe.txt", "unsafe")
        data = json.loads(self.meta.read_text())
        data["artifact_sha256"] = m.filehash(self.archive)
        self.meta.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "SHARD_UNSAFE_ORIGINAL_MEMBER"):
            m.cycle(self.root, (self.recipe,))

if __name__ == "__main__":
    unittest.main()
