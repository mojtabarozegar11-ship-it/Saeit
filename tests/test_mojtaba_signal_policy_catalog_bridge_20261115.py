"""Bridge test: the source-backed signal policy owns the fixed catalog."""
import unittest

from services.mojtaba_signal_policy import manual_signal_offer_for_plan

class SignalPolicyCatalogBridgeTests(unittest.TestCase):
    def test_policy_returns_fixed_manual_offer(self):
        result = manual_signal_offer_for_plan("education-weekly")
        self.assertEqual(result["agent"], "mojtaba.bot.ai")
        self.assertEqual(result["amount"], "9.90")
        self.assertTrue(result["content_policy_passed"])
        self.assertFalse(result["publication_allowed"])
        self.assertFalse(result["payment_received"])

    def test_unknown_plan_stays_blocked_at_policy_boundary(self):
        with self.assertRaises(ValueError):
            manual_signal_offer_for_plan("unknown-plan")

if __name__ == "__main__":
    unittest.main()
