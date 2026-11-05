"""Product provenance controls: evidence for another book is not F01 proof."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "factory_library_evidence_import", ROOT / "scripts/factory_library_evidence_import.py"
)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class EvidenceImportProvenanceTests(unittest.TestCase):
    def run_import(self, inbox, product, config):
        with patch.object(MOD, "CONFIG", config), patch.object(sys, "argv", [
            "factory_library_evidence_import.py", "--inbox", str(inbox), "--product-root", str(product)
        ]), contextlib.redirect_stdout(io.StringIO()) as output:
            MOD.main()
            return output.getvalue()

    def config(self, directory, *, actual_product="unrelated_mushroom_book", content=b"sample", include=True):
        name = "evidence.txt"
        record = {"name": name, "source_product_id": actual_product,
                  "sha256": hashlib.sha256(content).hexdigest()}
        spec = {"schema": "saeit.factory.library-evidence-import.v1",
                "product": "farm_enterprise_economics",
                "source_records": [record],
                "criteria_evidence": {"Q023": {"source": name}} if include else {}}
        path = Path(directory) / "plan.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        return path

    def test_historical_plan_has_no_admissible_product_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            inbox, product = base / "inbox", base / "product"
            inbox.mkdir(); product.mkdir()
            with self.assertRaisesRegex(SystemExit, "NO_PRODUCT_BOUND_EVIDENCE"):
                self.run_import(inbox, product, MOD.CONFIG)
            self.assertFalse((product / "evidence-inbox").exists())

    def test_cross_product_proof_is_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            inbox, product = base / "inbox", base / "product"
            inbox.mkdir(); product.mkdir()
            (inbox / "evidence.txt").write_bytes(b"sample")
            config = self.config(directory)
            with self.assertRaisesRegex(SystemExit, "EVIDENCE_SOURCE_PRODUCT_MISMATCH:Q023"):
                self.run_import(inbox, product, config)
            self.assertFalse((product / "evidence-inbox").exists())

    def test_matching_hash_and_product_only_import_as_unverified_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            inbox, product = base / "inbox", base / "product"
            inbox.mkdir(); product.mkdir()
            (inbox / "evidence.txt").write_bytes(b"sample")
            config = self.config(directory, actual_product="farm_enterprise_economics")
            output = self.run_import(inbox, product, config)
            candidate = json.loads((product / "global_quality_candidate.json").read_text())
            self.assertIn("FACTORY_INDEPENDENT_CERTIFICATION=FALSE", output)
            self.assertFalse(candidate["evidence_import"]["commercial_release_allowed"])
            self.assertEqual(candidate["criteria_evidence"]["Q023"]["path"], "evidence-inbox/evidence.txt")

    def test_missing_source_has_no_partial_destination_files(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            inbox, product = base / "inbox", base / "product"
            inbox.mkdir(); product.mkdir()
            config = self.config(directory, actual_product="farm_enterprise_economics")
            with self.assertRaisesRegex(SystemExit, "EVIDENCE_MISSING:evidence.txt"):
                self.run_import(inbox, product, config)
            self.assertFalse((product / "evidence-inbox").exists())


if __name__ == "__main__":
    unittest.main()
