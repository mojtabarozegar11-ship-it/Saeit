"""Acceptance and attack tests for bounded autonomous verification."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/factory_autonomous_evidence_verifier_v1.py"
SUPPLIER_PATH = ROOT / "scripts/factory_quality_evidence_supplier_v1.py"
AGENT_PATH = ROOT / "scripts/factory_ai_evidence_analyst_agent_v1.py"
EVALUATOR_PATH = ROOT / "scripts/factory_quality_evidence_evaluator_v1.py"
spec = importlib.util.spec_from_file_location("factory_auto_verifier_test", SCRIPT)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class AutonomousEvidenceVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.product = "sample_product"
        self.source = "a" * 64
        self.version = (self.root / "production-warehouse" / "finished"
                        / self.product / self.source)
        self.version.mkdir(parents=True)
        self.archive = self.version / "product.zip"
        with zipfile.ZipFile(self.archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr(self.product + "/README.md", "# Testable example\n")
            bundle.writestr(self.product + "/LICENSE.txt", "Copyright sample\n")
            bundle.writestr(self.product + "/test_sample.py",
                            "def test_sample():\n    assert 1 + 1 == 2\n")
        self.artifact = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.manifest = self.version / "warehouse_manifest.json"
        self.manifest.write_text(json.dumps({
            "schema": "saeit.factory.production-warehouse.v1",
            "product_id": self.product,
            "source_sha256": self.source,
            "artifact_sha256": self.artifact,
            "manufacturing_qc": "passed",
            "commercial_release": False,
            "site_transfer_state": "not_transferred",
            "bytes": self.archive.stat().st_size,
        }), encoding="utf8")
        self.catalog_path = self.root / "catalog.json"
        self.catalog_path.write_text(json.dumps({
            "schema": "saeit.factory.quality-100-groups.v2",
            "group_count": 100,
            "points_per_group": 10,
            "total_points": 1000,
            "groups": {
                "Q%03d" % n: {
                    "name": "Criterion %03d" % n,
                    "maximum_points": 10,
                    "quality_dimensions": [],
                } for n in range(1, 101)
            },
        }), encoding="utf8")
        self.supplier = verifier.load(SUPPLIER_PATH, "auto_supplier_fixture")
        self.agent = verifier.load(AGENT_PATH, "auto_agent_fixture")
        self.catalog = self.supplier.catalog(self.catalog_path)
        dossier = self.supplier.supplier_dossier(
            self.root, self.catalog, self.product, self.source, self.artifact)
        self.supplier_receipt = Path(self.supplier.persist(self.root, dossier)["receipt"])
        workpaper = self.agent.build_dossier(
            self.root, self.catalog, self.product, self.source,
            self.artifact, self.supplier)
        self.workpaper_receipt = Path(
            self.agent.persist(self.root, workpaper, self.supplier)["receipt"])

    def run_verifier(self):
        return verifier.run(self.root, self.catalog_path,
                            SUPPLIER_PATH, AGENT_PATH, EVALUATOR_PATH)

    def test_valid_zip_reverified_without_legal_or_release_claim(self):
        outcome = self.run_verifier()
        self.assertEqual(outcome["versions_seen"], 1)
        self.assertEqual(outcome["versions_machine_reverified"], 1)
        self.assertEqual(outcome["technical_criterion_checks"], 2)
        self.assertEqual(outcome["ai_workpapers_reproduced"], 100)
        location = (self.root / "quality-excellence" / "autonomous-verification"
                    / self.product / self.source)
        files = list(location.glob("verification-*.json"))
        self.assertEqual(len(files), 1)
        signed = json.loads(files[0].read_text(encoding="utf8"))
        self.assertEqual(signed["machine_measured_criteria_rechecked"], ["Q068", "Q092"])
        self.assertEqual(len(signed["technical_evidence_gaps_for_rework"]), 98)
        self.assertEqual(len(signed["criteria_missing_independent_quality_decisions"]), 100)
        self.assertFalse(signed["commercial_release_allowed"])
        self.assertFalse(signed["professional_quality_1000_certified"])
        self.assertFalse(signed["external_independence_claimed"])
        self.assertEqual(signed["signature_status"],
                         "UNSIGNED_MACHINE_RECEIPT_NOT_OWNER_SIGNATURE")
        self.assertEqual(self.run_verifier()["versions_machine_reverified"], 1)
        self.assertEqual(len(list(location.glob("verification-*.json"))), 1)

    def test_modified_archive_after_supply_is_rejected(self):
        self.archive.write_bytes(self.archive.read_bytes() + b"tampered")
        self.assertEqual(self.run_verifier()["versions_rejected"], 1)

    def test_modified_ai_workpaper_after_receipt_is_rejected(self):
        original = json.loads(self.workpaper_receipt.read_text(encoding="utf8"))
        original["professional_quality_1000_certified"] = True
        self.workpaper_receipt.write_text(json.dumps(original), encoding="utf8")
        outcome = self.run_verifier()
        self.assertEqual(outcome["versions_rejected"], 1)
        self.assertIn("DIGEST", outcome["rejected"][0]["reason"])

    def test_self_claimed_supplier_certification_is_not_accepted(self):
        original = json.loads(self.supplier_receipt.read_text(encoding="utf8"))
        original["professional_quality_1000_certified"] = True
        self.supplier_receipt.write_text(json.dumps(original), encoding="utf8")
        self.assertEqual(self.run_verifier()["versions_rejected"], 1)

    def test_missing_workpaper_causes_closed_gate(self):
        self.workpaper_receipt.rename(self.root / "quarantined.json")
        outcome = self.run_verifier()
        self.assertEqual(outcome["versions_rejected"], 1)
        self.assertEqual(outcome["commercial_releases"], 0)


if __name__ == "__main__":
    unittest.main()
