"""Real Stage-6 technical preflight; no invented expert/QA approvals."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(path, label):
    spec = importlib.util.spec_from_file_location(label, str(path))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


stage34 = load(ROOT / "scripts/factory_stage34_autonomous_handoff_20261023.py", "stage34_test_for_stage6")
stage5 = load(ROOT / "scripts/factory_stage5_evidence_workbook_20261023.py", "stage5_test_for_stage6")
stage6 = load(ROOT / "scripts/factory_stage6_preflight_rework_20261023.py", "stage6_under_test")
prior = load(ROOT / "tests/test_factory_stage34_autonomous_handoff_20261023.py", "factory_stage34_fixture_stage6")


class Stage6Audits(unittest.TestCase):
    def setUp(self):
        self.fixture = prior.Stage34Tests(methodName="test_both_stages_progress_with_real_evidence_and_no_public_claim")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.area = self.fixture.area
        self.name = self.fixture.name
        self.assertEqual(stage34.execute(self.root)["stage4_new"], 1)
        self.assertEqual(stage5.execute(self.root, stage34)["stage5_created_this_tick"], 1)

    def obj(self, relative):
        return json.loads((self.area / relative / self.name).read_text(encoding="utf-8"))

    def test_round_robin_fairness_over_batch_limit(self):
        names = ["order-a", "order-b", "order-c"]
        seen = []
        for _ in range(6):
            selected, path, state = stage6.fair_batch(self.area, names, 1, stage34)
            seen.extend(selected)
            stage34.atomic(path, state)
        self.assertEqual(seen, names + names)
        self.assertEqual(stage34.read(path)["next_index"], 0)
        self.assertEqual(stage6.fair_batch(self.area, names, 5, stage34)[0], names)

    def test_corrupt_cursor_fails_closed(self):
        cursor = self.area / "stage-06/round-robin-cursor.json"
        stage34.atomic(cursor, {"schema": "saeit.factory.stage6.round-robin.v1", "next_index": -1})
        with self.assertRaisesRegex(RuntimeError, "STAGE6_CURSOR_INVALID"):
            stage6.fair_batch(self.area, ["order-a"], 1, stage34)

    def test_real_bilingual_preflight_and_actionable_return(self):
        result = stage6.execute(self.root, stage34, stage5)
        self.assertEqual(result["stage6_inbox"], 1)
        self.assertEqual(result["stage6_technical_preflights_created_this_tick"], 1)
        self.assertEqual(result["stage5_substantive_rework_requests_total"], 1)
        self.assertEqual(result["stage6_integrity_blocked_this_tick"], 0)
        audit = self.obj("stage-06/technical-preflight")
        repair = self.obj("stage-05/substantive-rework-inbox")
        self.assertEqual(audit["stage5_manifest_sha256"],
                         stage34.digest(self.obj("stage-05/completed-drafts")))
        self.assertEqual(repair["stage6_preflight_sha256"], stage34.digest(audit))
        self.assertTrue(audit["integrity_preflight_passed"])
        self.assertEqual(len(audit["claim_audit_queue"]), 5)
        self.assertEqual(len(audit["source_audit_queue"]), 4)
        self.assertEqual(set(audit["bilingual_draft_measures"]), {"fa-IR", "en-US"})
        self.assertIn("METHOD_ONLY_DRAFT_NOT_SUBJECT_SPECIFIC_COMPLETED_MANUAL",
                      audit["blocking_findings"])
        self.assertFalse(audit["stage6_completed"])
        self.assertFalse(audit["stage7_authorized"])
        self.assertFalse(repair["independent_reviewer_signature_created"])
        self.assertFalse(result["websites_modified"])
        self.assertEqual(result["quality1000_certifications_created"], 0)
        self.assertFalse((self.area / "stage-07").exists())

    def test_repeat_is_idempotent(self):
        stage6.execute(self.root, stage34, stage5)
        again = stage6.execute(self.root, stage34, stage5)
        self.assertEqual(again["stage6_technical_preflights_created_this_tick"], 0)
        self.assertEqual(again["stage6_integrity_blocked_this_tick"], 0)
        self.assertEqual(again["stage5_substantive_rework_requests_total"], 1)

    def test_corrupt_draft_blocks_not_promotes(self):
        doc = self.area / "stage-05/drafts" / self.name[:-5] / "en-US.md"
        doc.write_text("spoofed replacement", encoding="utf-8")
        result = stage6.execute(self.root, stage34, stage5)
        self.assertEqual(result["stage6_integrity_blocked_this_tick"], 1)
        self.assertEqual(result["stage6_technical_preflights_total"], 0)
        self.assertEqual(result["stage7_approved_handoffs_created"], 0)
        self.assertIn("STAGE6_MANUSCRIPT_SHA_MISMATCH",
                      self.obj("stage-06/blocked")["reason"])

    def test_forged_human_approval_blocks(self):
        path = self.area / "stage-06/inbox" / self.name
        original = json.loads(path.read_text())
        original["human_review_completed"] = True
        stage34.atomic(path, original)
        result = stage6.execute(self.root, stage34, stage5)
        self.assertEqual(result["stage6_integrity_blocked_this_tick"], 1)
        self.assertEqual(result["stage6_technical_preflights_total"], 0)

    def test_symlinked_manuscript_blocks(self):
        root = self.area / "stage-05/drafts" / self.name[:-5]
        target = root / "en-US.md"
        target.unlink()
        target.symlink_to(root / "fa-IR.md")
        result = stage6.execute(self.root, stage34, stage5)
        self.assertEqual(result["stage6_integrity_blocked_this_tick"], 1)
        self.assertEqual(result["stage6_technical_preflights_total"], 0)

    def test_stage3_research_tampering_blocks(self):
        p = self.area / "stage-03/completed-designs" / self.name
        obj = json.loads(p.read_text())
        obj["chapters"][0]["source_ids"] = ["invented"]
        stage34.atomic(p, obj)
        result = stage6.execute(self.root, stage34, stage5)
        self.assertEqual(result["stage6_integrity_blocked_this_tick"], 1)
        self.assertFalse((self.area / "stage-05/substantive-rework-inbox" / self.name).exists())


if __name__ == "__main__":
    unittest.main()
