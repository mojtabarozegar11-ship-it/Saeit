import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "factory_quality_evidence_evaluator_v1.py"
if not PATH.is_file():
    PATH = Path(__file__).with_name("factory_quality_evidence_evaluator_v1.py")
spec = importlib.util.spec_from_file_location("evaluator", PATH)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class EvidenceEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.package = self.root / "sample_product.zip"
        with zipfile.ZipFile(self.package, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("sample_product/README.md", "scope limited test product\n")
            z.writestr("sample_product/test.txt", "real bytes\n")
        self.artifact_sha = sha(self.package.read_bytes())
        self.source_sha = "a" * 64
        self.catalog = {"Q%03d" % n: {"name": "criterion_%03d" % n}
                        for n in range(1, 101)}
        self.dossier = {
            "schema": e.SUPPLIER_SCHEMA,
            "product_id": "sample_product",
            "source_sha256": self.source_sha,
            "artifact_sha256": self.artifact_sha,
            "criteria_total": 100,
            "supplier_assignments": {
                key: {"criterion_id": key} for key in self.catalog
            },
            "automated_criteria_measured": ["Q068"],
            "q068_original_warehouse_zip_measurement": e.inspect_zip(
                self.package, "sample_product"),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_rechecks_exact_zip_and_never_awards_professional_quality(self):
        report = e.evaluate(self.dossier, self.package, self.catalog)
        self.assertEqual(report["machine_evidence_rechecked_criteria"], ["Q068"])
        self.assertEqual(report["criteria"]["Q068"]["machine_evidence_state"], "RECHECKED")
        self.assertEqual(report["machine_evidence_rechecked_count"], 1)
        self.assertIsNone(report["professional_quality_points"])
        self.assertEqual(report["independent_reviewer_count"], 0)
        self.assertFalse(report["release_allowed"])

    def test_rejects_package_hash_mismatch(self):
        self.dossier["artifact_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "ARTIFACT_HASH_MISMATCH"):
            e.evaluate(self.dossier, self.package, self.catalog)

    def test_rejects_forged_or_stale_q068_measurement(self):
        self.dossier["q068_original_warehouse_zip_measurement"]["members"][0]["sha256"] = "0" * 64
        report = e.evaluate(self.dossier, self.package, self.catalog)
        self.assertEqual(report["machine_evidence_rechecked_criteria"], [])
        self.assertEqual(report["rejected_claims"][0]["reason"],
                         "RECORDED_ZIP_MEASUREMENT_MISMATCH")

    def test_runtime_claim_from_non_pinned_build_is_never_accepted(self):
        self.dossier["automated_criteria_measured"] = ["Q068", "Q036"]
        report = e.evaluate(self.dossier, self.package, self.catalog)
        self.assertEqual(report["machine_evidence_rechecked_criteria"], ["Q068"])
        self.assertEqual(report["rejected_claims"], [{
            "criterion_id": "Q036", "reason": "NOT_TRUSTED_PINNED_F28_BUILD"}])

    def test_pinned_runtime_claim_requires_reexecution_and_receipt_match(self):
        with zipfile.ZipFile(self.package, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("greenhouse_crop_margin/README.md", "pinned runtime fixture\n")
        self.dossier["product_id"] = e.F28_RECIPE
        self.dossier["source_sha256"] = e.F28_SOURCE
        self.dossier["artifact_sha256"] = e.F28_ARTIFACT
        self.dossier["automated_criteria_measured"] = ["Q068", "Q036"]
        self.dossier["q068_original_warehouse_zip_measurement"] = e.inspect_zip(
            self.package, e.F28_RECIPE)
        measured = {"actual_embedded_unittest_count": 8,
                    "positive_baseline_cli_repeats": 8,
                    "invalid_cli_inputs_rejected": 8,
                    "repeat_stdout_sha256": "b" * 64}
        self.dossier["f28_runtime_technical_measurement"] = dict(measured)
        original_sha = e.digest
        e.digest = lambda data: e.F28_ARTIFACT if data == self.package.read_bytes() else original_sha(data)
        try:
            report = e.evaluate(self.dossier, self.package, self.catalog,
                                runtime_runner=lambda _: dict(measured))
            self.assertEqual(report["machine_evidence_rechecked_criteria"], ["Q036", "Q068"])
            self.dossier["f28_runtime_technical_measurement"]["invalid_cli_inputs_rejected"] = 7
            report = e.evaluate(self.dossier, self.package, self.catalog,
                                runtime_runner=lambda _: dict(measured))
            self.assertEqual(report["machine_evidence_rechecked_criteria"], ["Q068"])
            self.assertEqual(report["rejected_claims"][0]["reason"], "RUNTIME_RECHECK_FAILED")
        finally:
            e.digest = original_sha


if __name__ == "__main__":
    unittest.main()
