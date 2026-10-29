"""Rights gate: private evidence must bind every shipped byte before release."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts" / "factory_product_rights_clearance_v1.py"
spec = importlib.util.spec_from_file_location("product_rights_gate", SRC)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ProductRightsGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root / "release.zip"
        with zipfile.ZipFile(self.package, "w") as archive:
            archive.writestr("product/readme.txt", "release")
        self.sha = hashlib.sha256(self.package.read_bytes()).hexdigest()

    def test_missing_signed_rights_evidence_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "RIGHTS_CLEARANCE_EVIDENCE_MISSING"):
            gate.require_rights_clearance(
                self.root, "sample_product", self.sha, self.package
            )

    def test_wrong_product_hash_is_rejected_before_any_clearance(self):
        with self.assertRaisesRegex(ValueError, "RIGHTS_ARTIFACT_HASH_MISMATCH"):
            gate.require_rights_clearance(
                self.root, "sample_product", "0" * 64, self.package
            )

    def test_manifest_must_cover_each_exact_zip_member(self):
        inbox = self.root / "inbox"
        digest = self.sha
        directory = inbox / "rights-clearance" / "sample_product" / digest
        directory.mkdir(parents=True)
        (inbox / "rights-evidence").mkdir()
        (inbox / "quality-trust").mkdir()
        (inbox / "quality-trust" / "trusted-reviewers.json").write_text("{}")
        manifest = {
            "schema": gate.SCHEMA,
            "recipe": "sample_product",
            "artifact_sha256": digest,
            "territory": "declared territory",
            "term": "declared term",
            "public_distribution": True,
            "commercial_distribution": False,
            "components": [],
        }
        (directory / "rights-manifest.json").write_text(json.dumps(manifest))
        (directory / "signed-clearance.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "RIGHTS_COMPONENT_INVENTORY_INCOMPLETE"):
            gate.require_rights_clearance(
                inbox, "sample_product", digest, self.package
            )


if __name__ == "__main__":
    unittest.main()
