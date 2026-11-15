"""Integration checks for the Moj Prop level-10 governance lock."""
from __future__ import annotations

from unittest import TestCase

from prop_firm.level10_lock import (
    OWNER_DECISION_LEVEL_CAPITAL_USD,
    OWNER_DECISION_LEVEL_NUMBER,
    REQUIRED_LEVEL_10_ATTESTATIONS,
    evaluate_level_lock,
)
from prop_firm.policy_integrity import policy_drift_defects, policy_integrity_report


class MojPropLevel10IntegrationTests(TestCase):
    def test_level10_contract_is_part_of_canonical_policy_integrity(self):
        self.assertEqual(OWNER_DECISION_LEVEL_NUMBER, 10)
        self.assertEqual(OWNER_DECISION_LEVEL_CAPITAL_USD, 35000)
        self.assertEqual(len(REQUIRED_LEVEL_10_ATTESTATIONS), 6)
        self.assertEqual(policy_drift_defects(), ())

    def test_default_level10_decision_remains_locked(self):
        decision = evaluate_level_lock(level_number=10)
        self.assertTrue(decision.locked)
        self.assertIn("owner_decision_recorded", decision.missing)
        self.assertFalse(decision.checkout_enabled)
        self.assertFalse(decision.trading_enabled)
        self.assertFalse(decision.payout_enabled)

    def test_integrity_report_declares_no_authorization_side_effect(self):
        report = policy_integrity_report()
        self.assertTrue(report["source_policy_consistent"])
        self.assertEqual(report["defects"], [])
        self.assertFalse(report["payment_or_trading_authorized"])
