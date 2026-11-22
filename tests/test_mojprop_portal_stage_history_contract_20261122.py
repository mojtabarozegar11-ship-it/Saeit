from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PORTAL = ROOT / "prop_firm" / "customer_portal_views.py"


class SimulationStagePortalContractTests(unittest.TestCase):
    def test_portal_reads_stage_receipts_without_transition_or_payout_side_effects(self):
        source = PORTAL.read_text(encoding="utf-8")
        start = source.index("def _stage_history(")
        end = source.index("\n\ndef _secured(", start)
        helper = source[start:end]
        self.assertIn("PropSimulationStageTransition.objects.using(MOJPROP_DB_ALIAS)", helper)
        self.assertIn('.filter(account_id=account_id)', helper)
        self.assertNotIn("commit_next_simulated_level", helper)
        self.assertNotIn("commit_full_profit_payout", helper)
        self.assertNotIn("send_trx", helper)
        self.assertNotIn("issue_invoice", helper)
        self.assertNotIn("settle_invoice", helper)
        self.assertIn('_stage_history(account["id"])', source)


if __name__ == "__main__":
    unittest.main()
