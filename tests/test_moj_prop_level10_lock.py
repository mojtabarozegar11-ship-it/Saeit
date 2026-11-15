"""Tests for the canonical Moj Prop level-10 owner decision lock."""
from decimal import Decimal

from django.test import SimpleTestCase

from prop_firm.level10_lock import (
    OWNER_DECISION_LEVEL_CAPITAL_USD,
    OWNER_DECISION_LEVEL_INDEX,
    OWNER_DECISION_LEVEL_NUMBER,
    REQUIRED_LEVEL_10_ATTESTATIONS,
    evaluate_level_lock,
    level10_lock_summary,
)


class MojPropLevel10LockTests(SimpleTestCase):
    def test_level_ten_is_the_tenth_ordinal_and_35000_capital_anchor(self):
        self.assertEqual(OWNER_DECISION_LEVEL_NUMBER, 10)
        self.assertEqual(OWNER_DECISION_LEVEL_INDEX, 9)
        self.assertEqual(OWNER_DECISION_LEVEL_CAPITAL_USD, Decimal("35000"))

    def test_levels_below_ten_do_not_require_owner_decision_attestation(self):
        decision = evaluate_level_lock(level_number=9)
        self.assertFalse(decision.owner_decision_required)
        self.assertFalse(decision.locked)
        self.assertEqual(decision.missing, ())
        self.assertFalse(decision.checkout_enabled)
        self.assertFalse(decision.trading_enabled)

    def test_level_ten_is_locked_by_default(self):
        decision = evaluate_level_lock(level_number=10)
        self.assertTrue(decision.owner_decision_required)
        self.assertTrue(decision.locked)
        self.assertEqual(decision.capital_usd, Decimal("35000"))
        self.assertEqual(decision.missing, REQUIRED_LEVEL_10_ATTESTATIONS)
        self.assertFalse(decision.checkout_enabled)
        self.assertFalse(decision.trading_enabled)
        self.assertFalse(decision.payout_enabled)

    def test_truthy_strings_cannot_unlock_level_ten(self):
        decision = evaluate_level_lock(
            level_number=10,
            attestations={key: "approved" for key in REQUIRED_LEVEL_10_ATTESTATIONS},
        )
        self.assertTrue(decision.locked)
        self.assertEqual(decision.missing, REQUIRED_LEVEL_10_ATTESTATIONS)

    def test_complete_attestations_remove_only_the_governance_lock(self):
        decision = evaluate_level_lock(
            level_number=10,
            attestations={key: True for key in REQUIRED_LEVEL_10_ATTESTATIONS},
        )
        self.assertFalse(decision.locked)
        self.assertEqual(decision.missing, ())
        self.assertFalse(decision.checkout_enabled)
        self.assertFalse(decision.trading_enabled)
        self.assertFalse(decision.payout_enabled)

    def test_higher_levels_remain_locked_without_the_same_gate(self):
        decision = evaluate_level_lock(level_number=14)
        self.assertTrue(decision.owner_decision_required)
        self.assertTrue(decision.locked)
        self.assertEqual(decision.missing, REQUIRED_LEVEL_10_ATTESTATIONS)

    def test_summary_is_safe_and_explicit(self):
        summary = level10_lock_summary()
        self.assertEqual(summary["decision_level_number"], 10)
        self.assertTrue(summary["locked_by_default"])
        self.assertEqual(summary["decision_level_capital_usd"], "35000")
        self.assertFalse(summary["checkout_enabled"])
        self.assertFalse(summary["trading_enabled"])
        self.assertFalse(summary["payout_enabled"])

    def test_invalid_level_and_attestation_shapes_fail_closed(self):
        for value in (True, 0, 15, "10"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    evaluate_level_lock(level_number=value)
        with self.assertRaises(ValueError):
            evaluate_level_lock(level_number=10, attestations=[])
