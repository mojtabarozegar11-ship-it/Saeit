"""The live ZIP inventory must reject stale, incomplete and corrupted bundles."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "product_recipes/farm_enterprise_economics"
SPEC = importlib.util.spec_from_file_location(
    "f01_vps_exact_zip_readonly", ROOT / "scripts/f01_vps_exact_zip_readonly.py"
)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
HASHES = tuple(hashlib.sha256((RECIPE / name).read_bytes()).hexdigest()
               for name in MOD.FILES)


class ExactZipReadOnlyTests(unittest.TestCase):
    def make_product(self, base, *, omit=None, stale=None, corrupted_manifest=False):
        directory = base / "digital-products" / MOD.PRODUCT
        directory.mkdir(parents=True)
        archive = directory / (MOD.PRODUCT + "-internal-qa.zip")
        with zipfile.ZipFile(archive, "w") as output:
            for filename in MOD.FILES:
                if filename != omit:
                    content = b"stale" if filename == stale else (RECIPE / filename).read_bytes()
                    output.writestr(MOD.PRODUCT + "/" + filename, content)
        manifest = {
            "recipe": MOD.PRODUCT,
            "qa_status": "passed",
            "commercial_status": "private_internal_qa_pass_not_published",
            "public_listing_enabled": False,
            "owner_publication_approval": False,
            "artifact_sha256": "0" * 64 if corrupted_manifest else MOD.file_sha(archive),
        }
        (directory / "manufacturing_manifest.json").write_text(json.dumps(manifest))
        return directory

    def test_exact_private_archive_is_source_matched_but_not_certified(self):
        with tempfile.TemporaryDirectory() as temp:
            self.make_product(Path(temp))
            result = MOD.probe(Path(temp), HASHES)
            self.assertTrue(result["seven_source_files_match_reviewed_commit"])
            self.assertFalse(result["quality_1000_approved"])
            self.assertFalse(result["commercial_release_allowed"])

    def test_missing_customer_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            self.make_product(Path(temp), omit="guided_start.py")
            result = MOD.probe(Path(temp), HASHES)
            self.assertFalse(result["seven_source_files_match_reviewed_commit"])
            self.assertIn("guided_start.py", result["missing_or_mismatched_source_files"])

    def test_changed_bytes_and_manifest_sha_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            self.make_product(Path(temp), stale="calculator.py", corrupted_manifest=True)
            result = MOD.probe(Path(temp), HASHES)
            self.assertFalse(result["seven_source_files_match_reviewed_commit"])
            self.assertIn("calculator.py", result["missing_or_mismatched_source_files"])
            self.assertFalse(result["manifest_artifact_sha_matches"])


if __name__ == "__main__":
    unittest.main()
