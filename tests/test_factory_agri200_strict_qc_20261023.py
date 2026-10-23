"""Strict 1000/1000 agricultural QC and immutable rework loop."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


stage34 = load(ROOT / "scripts/factory_stage34_autonomous_handoff_20261023.py", "s34_strict")
stage5 = load(ROOT / "scripts/factory_stage5_evidence_workbook_20261023.py", "s5_strict")
maker = load(ROOT / "scripts/factory_agri200_downloadable_20261023.py", "maker_strict")
auditor = load(ROOT / "scripts/factory_agri200_strict_qc_20261023.py", "auditor_strict")
fixtures = load(ROOT / "tests/test_factory_stage34_autonomous_handoff_20261023.py", "fixture_strict")
CATALOG = ROOT / "factory_config/quality_100_criteria.json"


class StrictQualityTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.Stage34Tests(
            methodName="test_both_stages_progress_with_real_evidence_and_no_public_claim")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root, self.area, self.name = fixture.root, fixture.area, fixture.name
        self.assertEqual(stage34.execute(self.root)["stage4_new"], 1)
        self.assertEqual(stage5.execute(self.root, stage34)["stage5_created_this_tick"], 1)
        self.rubric = auditor.criteria(CATALOG)

    def read(self, folder):
        return stage34.read(self.area / folder / self.name)

    def run_qc(self, batch=250):
        return auditor.execute(self.root, stage34, stage5, self.rubric, batch)

    def test_private_real_zip_is_still_rejected_as_an_unreviewed_manual(self):
        self.assertTrue(maker.package_one(self.area, self.name, stage34, stage5))
        result = self.run_qc()
        self.assertEqual(result["new_strict_qc1000_audits"], 1)
        self.assertEqual(result["returned_to_rework_total"], 1)
        report = self.read("stage-06/strict-qc1000")
        ticket = self.read("stage-05/strict-qc-rework")
        self.assertEqual(report["criteria_required"], 100)
        self.assertEqual(report["required_points"], 1000)
        self.assertEqual(set(report["criteria"]), set(self.rubric))
        self.assertTrue(all(v["independently_verified_points"] is None
                            for v in report["criteria"].values()))
        self.assertTrue(report["technical_package_integrity_passed"])
        self.assertEqual(report["disposition"], "RETURN_TO_PRODUCTION")
        self.assertIn("P0_METHODS_ONLY_NOT_A_SUBJECT_SPECIFIC_SCIENTIFIC_PRODUCT",
                      report["critical_findings"])
        self.assertFalse(report["quality1000_approved"])
        self.assertFalse(report["public_distribution_allowed"])
        self.assertEqual(ticket["strict_qc_report_sha256"], stage34.digest(report))
        self.assertTrue(ticket["must_resubmit_new_artifact_and_repeat_strict_qc"])
        self.assertFalse((self.area / "stage-07").exists())

    def test_a_corrupt_artifact_is_quarantined_and_never_approved(self):
        maker.package_one(self.area, self.name, stage34, stage5)
        receipt = self.read("stage-05/downloadable-receipts")
        archive = self.area / receipt["archive_relative_path"]
        archive.write_bytes(archive.read_bytes() + b"tampered")
        report = self.run_qc()
        self.assertEqual(report["quarantined_during_this_run"], 1)
        item = self.read("stage-06/strict-qc1000")
        self.assertEqual(item["disposition"], "QUARANTINE_INTEGRITY")
        self.assertTrue(any("P0_INTEGRITY:" in c for c in item["critical_findings"]))
        self.assertFalse(item["quality1000_approved"])

    def test_missing_zip_returns_to_engineering_not_approval(self):
        result = self.run_qc()
        self.assertEqual(result["new_strict_qc1000_audits"], 1)
        item = self.read("stage-06/strict-qc1000")
        self.assertIn("P0_DOWNLOADABLE_CANDIDATE_NOT_BUILT",
                      item["critical_findings"])
        self.assertFalse(item["technical_package_integrity_passed"])
        self.assertFalse(item["commercial_release"])

    def test_idempotency_and_immutable_report_rejects_mutation(self):
        maker.package_one(self.area, self.name, stage34, stage5)
        first = self.run_qc()
        second = self.run_qc()
        self.assertEqual(first["new_strict_qc1000_audits"], 1)
        self.assertEqual(second["new_strict_qc1000_audits"], 0)
        self.assertEqual(second["audit_execution_blocked"], 0)
        receipt = self.read("stage-05/downloadable-receipts")
        (self.area / receipt["archive_relative_path"]).write_bytes(b"spoofed")
        after = self.run_qc()
        self.assertEqual(after["audit_execution_blocked"], 1)
        self.assertIn("IMMUTABLE_OUTPUT_CONFLICT",
                      self.read("stage-06/strict-qc-blocked")["error"])

    def test_stage5_identity_forgery_cannot_gain_approval(self):
        maker.package_one(self.area, self.name, stage34, stage5)
        path = self.area / "stage-05/completed-drafts" / self.name
        forged = stage34.read(path)
        forged["quality1000_approved"] = True
        stage34.atomic(path, forged)
        result = self.run_qc()
        self.assertEqual(result["audit_execution_blocked"], 1)
        self.assertFalse((self.area / "stage-06/strict-qc1000" / self.name).exists())

    def test_catalog_must_contain_all_100_gates(self):
        self.assertEqual(len(self.rubric), 100)
        self.assertEqual(self.rubric["Q001"]["maximum_points"], 10)
        bad = self.area / "fake-catalog.json"
        stage34.atomic(bad, {"schema": "invalid", "total_points": 999,
                             "groups": {}})
        with self.assertRaisesRegex(RuntimeError, "CATALOG_NOT_1000"):
            auditor.criteria(bad)

    def test_cursor_fairly_covers_more_than_one_batch(self):
        # Mimic two stage-5 orders using the generated validated fixture.
        original = self.name
        replacement = original.replace("r001", "r002")
        source = self.area / "stage-05/completed-drafts" / original
        second = self.area / "stage-05/completed-drafts" / replacement
        second.write_bytes(source.read_bytes())
        first = self.run_qc(batch=1)
        second_run = self.run_qc(batch=1)
        self.assertEqual(first["inspected_this_run"], 1)
        self.assertEqual(second_run["inspected_this_run"], 1)
        self.assertEqual(first["audit_execution_blocked"], 0)
        self.assertEqual(second_run["audit_execution_blocked"], 1)
        self.assertEqual(stage34.read(self.area / "stage-06/strict-qc-blocked" / replacement)["order_file"], replacement)


if __name__ == "__main__":
    unittest.main()
