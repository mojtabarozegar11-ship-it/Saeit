"""No-budget-bypass regressions for exact Stage4 guarded resume patch."""
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[1]/"scripts/factory_stage4_evidence_revision_resume_20261021.py"
spec=importlib.util.spec_from_file_location("stage4_guard",str(PATH))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Stage4RevisionResume(unittest.TestCase):
    def test_one_live_wait_branch_only_and_idempotent(self):
        source="def plan(state,progress,due,timezone):\n"+m.OLD+"\n"
        changed,ok=m.patch_text(source)
        self.assertTrue(ok)
        self.assertIn("0 < len(current_evidence) <= 100",changed)
        self.assertIn("and current_evidence != prior_evidence",changed)
        self.assertIn("if not revised_evidence:",changed)
        self.assertIn("action\": \"waiting_for_evidence",changed)
        self.assertIn("from .factory_stage4 import effective_research",changed)
        self.assertEqual(m.patch_text(changed),(changed,False))
    def test_unrecognized_source_and_duplicate_branch_are_refused(self):
        with self.assertRaisesRegex(RuntimeError,"EXACT_PREIMAGE"):
            m.patch_text("def bogus(): pass")
        with self.assertRaisesRegex(RuntimeError,"EXACT_PREIMAGE"):
            m.patch_text("def outer():\n"+m.OLD+"\n"+m.OLD)
    def test_no_new_evidence_never_resumes(self):
        sample=[{"real_source_id":"A"}]
        self.assertFalse(m.evidence_revised(sample,sample))
        self.assertFalse(m.evidence_revised([],[]))
        self.assertFalse(m.evidence_revised([],None))
        self.assertFalse(m.evidence_revised([],["A"]*101))
        self.assertFalse(m.evidence_revised(["A"]*100,["B"]*101))
        self.assertTrue(m.evidence_revised(["A"],["B"]))
        self.assertTrue(m.evidence_revised(["A"]*100,["B"]*100))
    def test_patch_does_not_touch_factories_or_authorize_sales(self):
        change=m.NEW
        self.assertNotIn("commercial_release_allowed=True",change)
        self.assertNotIn("FACTORY_RESEARCH_MAX_ATTEMPTS",change)
        self.assertNotIn("1000",change)
        self.assertNotIn("product.state",change)
        self.assertIn("waiting_for_evidence",change)

if __name__=="__main__":unittest.main()
