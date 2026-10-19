"""Actual ledger remediation tasks, no invented citations, safe idempotency."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "saeit_research_triage", str(ROOT/"scripts/factory_research_triage.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ResearchTriage(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root/"research-rework").mkdir()

    def make(self, number, reasons=None):
        reasons = reasons if reasons is not None else [
            "FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED",
            "ONE_STRUCTURED_INTERNAL_RESEARCH_ACTION_REQUIRED"]
        directory = self.root/"research-rework"/("product-%d" % number)
        directory.mkdir()
        (directory/"ledger.json").write_text(json.dumps({
            "schema": "saeit.factory.research-rework.v1", "product_id": number,
            "current_status": "research_correction_required",
            "history": [{"fingerprint": "a"*64, "blocking_reasons": reasons}]}), encoding="utf8")

    def test_209_real_ledgers_have_209_plans_and_zero_fake_approvals(self):
        for n in range(1, 210):
            self.make(n)
        status = module.snapshot(self.root)
        self.assertEqual(status["research_ledgers_found"], 209)
        self.assertEqual(status["workplans_created_or_updated"], 209)
        self.assertEqual(status["genuine_research_repairs_verified_this_run"], 0)
        for n in range(1, 210):
            task = json.loads((self.root/"research-triage"/("product-%d.json"%n)).read_text())
            self.assertFalse(task["research_evidence_confirmed_complete"])
            self.assertFalse(task["commercial_approval_claimed"])
            self.assertEqual(len(task["required_fixes"]), 2)
        again = module.snapshot(self.root)
        self.assertEqual(again["workplans_created_or_updated"], 0)

    def test_unrecognized_reason_fails_closed(self):
        self.make(7, ["unverified_new_reason"])
        with self.assertRaisesRegex(RuntimeError, "UNRECOGNIZED_REASON"):
            module.snapshot(self.root)
        self.assertFalse((self.root/"research-triage/product-7.json").exists())

    def test_original_ledger_is_not_modified(self):
        self.make(3)
        p = self.root/"research-rework/product-3/ledger.json"
        before = p.read_bytes()
        module.snapshot(self.root)
        self.assertEqual(p.read_bytes(), before)

    def test_updated_ledger_revises_plan_not_quality_approval(self):
        self.make(5)
        module.snapshot(self.root)
        p = self.root/"research-rework/product-5/ledger.json"
        data = json.loads(p.read_text())
        data["history"].append({"fingerprint": "b"*64,
                                "blocking_reasons": ["TEN_FACTOR_VALIDATION_PASS_REQUIRED"]})
        p.write_text(json.dumps(data))
        new_status = module.snapshot(self.root)
        self.assertEqual(new_status["workplans_created_or_updated"], 1)
        out = json.loads((self.root/"research-triage/product-5.json").read_text())
        self.assertEqual(out["required_fixes"][0]["deliverable"], "ten_dimension_assessment")
        self.assertFalse(out["research_evidence_confirmed_complete"])


if __name__ == "__main__":
    unittest.main()
