"""Fail-closed tests of genuine immutable Stage5 rework artifact generation."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

stage34 = load(ROOT / "scripts/factory_stage34_autonomous_handoff_20261023.py", "stage34_rework_tests")
stage5 = load(ROOT / "scripts/factory_stage5_evidence_workbook_20261023.py", "stage5_rework_tests")
stage6 = load(ROOT / "scripts/factory_stage6_preflight_rework_20261023.py", "stage6_rework_tests")
rework = load(ROOT / "scripts/factory_stage5_substantive_rework_20261023.py", "substantive_rework_tests")
fixture_module = load(ROOT / "tests/test_factory_stage34_autonomous_handoff_20261023.py", "fixtures_rework_tests")

class SubstantiveRework(unittest.TestCase):
    def setUp(self):
        fixture = fixture_module.Stage34Tests(
            methodName="test_both_stages_progress_with_real_evidence_and_no_public_claim")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root, self.area, self.name = fixture.root, fixture.area, fixture.name
        self.assertEqual(stage34.execute(self.root)["stage4_new"], 1)
        self.assertEqual(stage5.execute(self.root, stage34)["stage5_created_this_tick"], 1)
        self.assertEqual(stage6.execute(self.root, stage34, stage5)[
            "stage6_technical_preflights_created_this_tick"], 1)

    def read(self, folder):
        return stage34.read(self.area / folder / self.name)

    def test_real_versioned_bilingual_evidence_and_source_links(self):
        report = rework.execute(self.root, stage34, stage5, stage6)
        self.assertEqual(report["source_specific_revision_briefs_created_this_run"], 1)
        self.assertEqual(report["blocked_this_run"], 0)
        self.assertEqual(report["qa1000_approvals"], 0)
        self.assertFalse(report["sites_changed"])
        manifest = self.read("stage-05/substantive-revision-manifests")
        reviewer = self.read("stage-06/substantive-review-inbox")
        self.assertEqual(reviewer["revision_manifest_sha256"], stage34.digest(manifest))
        self.assertEqual(manifest["manuscript_revision"], 2)
        self.assertFalse(manifest["substantive_full_text_authoring_completed"])
        self.assertFalse(manifest["independent_scientific_review"])
        self.assertFalse(manifest["public_distribution_allowed"])
        for loc in ("fa-IR", "en-US"):
            target = self.area / "stage-05/substantive-revisions" / self.name[:-5] / "v002" / (loc + ".md")
            self.assertTrue(target.is_file())
            self.assertEqual(rework.sha(target.read_bytes()), manifest["manuscript_sha256"][loc])
            self.assertIn("Indexed research excerpt", target.read_text())
            self.assertIn("Genuine bibliographic test source", target.read_text())
        self.assertFalse((self.area / "stage-07").exists())

    def test_idempotent_repeated_run_without_duplicate_revision(self):
        first = rework.execute(self.root, stage34, stage5, stage6)
        second = rework.execute(self.root, stage34, stage5, stage6)
        self.assertEqual(first["source_specific_revision_briefs_created_this_run"], 1)
        self.assertEqual(second["source_specific_revision_briefs_created_this_run"], 0)
        self.assertEqual(second["blocked_this_run"], 0)
        self.assertEqual(second["source_specific_revision_briefs_total"], 1)

    def test_modified_claim_blocks_without_republication(self):
        target = self.area / "stage-02/completed-dossiers" / self.name
        claim = stage34.read(target)
        claim["claims"][0]["statement"] = "unverified"
        stage34.atomic(target, claim)
        outcome = rework.execute(self.root, stage34, stage5, stage6)
        self.assertEqual(outcome["blocked_this_run"], 1)
        self.assertFalse((self.area / "stage-05/substantive-revision-manifests" / self.name).exists())

    def test_forged_review_signature_cannot_pass(self):
        path = self.area / "stage-05/substantive-rework-inbox" / self.name
        payload = stage34.read(path)
        payload["quality1000_approved"] = True
        stage34.atomic(path, payload)
        outcome = rework.execute(self.root, stage34, stage5, stage6)
        self.assertEqual(outcome["blocked_this_run"], 1)
        self.assertFalse((self.area / "stage-06/substantive-review-inbox" / self.name).exists())

    def test_immutable_revision_tampering_is_not_hidden(self):
        rework.execute(self.root, stage34, stage5, stage6)
        target = self.area / "stage-05/substantive-revisions" / self.name[:-5] / "v002/en-US.md"
        target.write_text("tampered", encoding="utf-8")
        outcome = rework.execute(self.root, stage34, stage5, stage6)
        self.assertEqual(outcome["blocked_this_run"], 1)
        self.assertEqual(target.read_text(), "tampered")

    def test_missing_preflight_blocks(self):
        (self.area / "stage-06/technical-preflight" / self.name).unlink()
        result = rework.execute(self.root, stage34, stage5, stage6)
        self.assertEqual(result["blocked_this_run"], 1)
        self.assertEqual(result["source_specific_revision_briefs_total"], 0)

if __name__ == "__main__":
    unittest.main()
