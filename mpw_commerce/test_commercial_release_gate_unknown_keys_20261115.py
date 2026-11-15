"""Release evidence typos must not produce a false technical pass."""
import unittest

from mpw_commerce.commercial_release_gate import REQUIRED_GATES, evaluate_commercial_release


class CommercialReleaseUnknownKeyTests(unittest.TestCase):
    def test_unknown_evidence_key_blocks_even_when_required_checks_are_true(self):
        checks = {name: True for name in REQUIRED_GATES}
        checks["buyer_email_owend"] = True
        result = evaluate_commercial_release(checks)
        self.assertFalse(result["technical_gate_passed"])
        self.assertEqual(result["unknown_gates"], ["buyer_email_owend"])
        self.assertFalse(result["payment_enabled"])
        self.assertFalse(result["production_activation_allowed"])

    def test_known_evidence_keys_report_no_unknowns(self):
        result = evaluate_commercial_release({name: True for name in REQUIRED_GATES})
        self.assertEqual(result["unknown_gates"], [])
        self.assertTrue(result["technical_gate_passed"])
        self.assertFalse(result["production_activation_allowed"])


if __name__ == "__main__":
    unittest.main()
