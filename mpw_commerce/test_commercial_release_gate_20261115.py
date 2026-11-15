"""Regression tests for the MojPlayWin commercial release gate."""
import unittest

from mpw_commerce.commercial_release_gate import (
    REQUIRED_GATES, evaluate_commercial_release,
)

class CommercialReleaseGateTests(unittest.TestCase):
    def test_empty_evidence_is_fail_closed(self):
        result = evaluate_commercial_release({})
        self.assertFalse(result["technical_gate_passed"])
        self.assertEqual(result["missing_gates"], list(REQUIRED_GATES))
        self.assertFalse(result["payment_enabled"])
        self.assertFalse(result["production_activation_allowed"])
        self.assertTrue(result["requires_owner_confirmation"])

    def test_partial_evidence_lists_exact_missing_gates(self):
        result = evaluate_commercial_release({
            "source_closure_verified": True,
            "buyer_email_owned": True,
        })
        self.assertFalse(result["technical_gate_passed"])
        self.assertIn("migrations_verified", result["missing_gates"])
        self.assertNotIn("source_closure_verified", result["missing_gates"])

    def test_all_technical_gates_still_do_not_auto_activate_production(self):
        evidence = {name: True for name in REQUIRED_GATES}
        result = evaluate_commercial_release(evidence)
        self.assertTrue(result["technical_gate_passed"])
        self.assertEqual(result["missing_gates"], [])
        self.assertFalse(result["payment_enabled"])
        self.assertFalse(result["production_activation_allowed"])
        self.assertFalse(result["revenue_proven"])

    def test_non_mapping_input_is_rejected(self):
        with self.assertRaises(TypeError):
            evaluate_commercial_release(None)

if __name__ == "__main__":
    unittest.main()
