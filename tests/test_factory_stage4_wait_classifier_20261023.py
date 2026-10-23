import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/factory_stage4_wait_classifier_20261023.py"
spec = importlib.util.spec_from_file_location("stage4_wait_classifier", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class WaitClassified(unittest.TestCase):
    def source(self):
        return ("def replan(state, progress, due, timezone):\n"
                "            if progress.get(\"status\") == \"capacity_exhausted\" or (due and due > timezone.now()):\n"
                "                prior_evidence = []\n"
                "                current_evidence = []\n"
                "                revised_evidence = (0 < len(current_evidence) <= 100 and current_evidence != prior_evidence)\n"
                + mod.CONTEXT + mod.OLD + "\n")

    def test_two_sequential_distinct_changes_and_idempotency(self):
        p1, p2, changed = mod.transform(self.source())
        self.assertTrue(changed)
        self.assertNotEqual(p1, self.source())
        self.assertNotEqual(p2, p1)
        self.assertIn("independent new evidence", p1)
        self.assertIn("wait_code", p2)
        self.assertIn("next_retry_at", p2)
        self.assertIn("external_evidence_required", p2)
        self.assertIn("current_evidence != prior_evidence", p2)
        self.assertEqual(mod.transform(p2), (p2, p2, False))

    def test_unexpected_code_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError,"PREIMAGE_MISMATCH"):
            mod.transform("def wrong(): pass")
        with self.assertRaisesRegex(RuntimeError,"PREIMAGE_MISMATCH"):
            mod.transform(self.source() + mod.OLD)

    def test_no_cap_or_approval_bypass(self):
        p1, p2, _ = mod.transform(self.source())
        for value in (p1, p2):
            self.assertIn("0 < len(current_evidence) <= 100", value)
            self.assertIn("if not revised_evidence", value)
            self.assertNotIn("commercial_release=True", value)
            self.assertNotIn("quality_1000_certified=True", value)

if __name__ == "__main__":
    unittest.main()
