from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "deploy" / "staging" / "MOJPROP_RELEASE_RUNBOOK.md"


class MojPropReleaseRunbookContractTests(unittest.TestCase):
    def test_runbook_matches_current_candidate_and_has_hard_stops(self):
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("0008_simulation_stage_transition", text)
        self.assertIn("migrate prop_firm --database=mojprop --plan", text)
        self.assertIn("Saeit-mojplaywin-integrated-20261119", text)
        self.assertIn("physically separate MariaDB database", text)
        self.assertIn("Never reverse a production", text)
        self.assertNotIn("Run migration 0011_simulation_isolation", text)


if __name__ == "__main__":
    unittest.main()
