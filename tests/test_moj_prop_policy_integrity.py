"""Canonical Moj Prop policy admission; no money, broker or production access."""
from dataclasses import replace
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase
from core.tron_tenant_policy import TenantDecision, REQUIRED_ATTESTATIONS
from prop_firm.challenge_commerce import REQUIRED, assess_challenge_checkout
from prop_firm.plans import CHALLENGE_PLANS
from prop_firm.policy_integrity import (
    CANONICAL_CONTRACT_ID, policy_drift_defects, policy_integrity_report,
)
from prop_firm.rules import POLICY


class PolicyIntegrityTests(SimpleTestCase):
    def review(self):
        return assess_challenge_checkout(
            merchant_tenant=TenantDecision(
                "moj-prop-merchant", "mojplaywin.com", "moj_prop", True, (),
            ),
            free_treasury_usd="1000", protected_reserves_usd="100",
            attestations={key: True for key in REQUIRED},
            trusted_merchant_registry={
                ("mojplaywin.com", "moj_prop"): {
                    "tenant_id": "moj-prop-merchant",
                    "network": "tron-mainnet", "asset": "TRX",
                    **{key: True for key in REQUIRED_ATTESTATIONS},
                },
            },
        )

    def test_current_official_fourteen_level_two_stage_policy_consistent(self):
        self.assertEqual(policy_drift_defects(), ())
        report = policy_integrity_report()
        self.assertEqual(report["checked_invariants"], 19)
        self.assertEqual(report["canonical_contract_id"], CANONICAL_CONTRACT_ID)
        self.assertTrue(report["source_policy_consistent"])
        self.assertFalse(report["payment_or_trading_authorized"])

    def test_shadow_nine_level_contract_stays_noncanonical(self):
        import prop_firm.policy_integrity as integrity
        with patch.object(integrity, "LEVELS", integrity.LEVELS[:9]):
            self.assertIn("14_level_ladder", policy_drift_defects())
            self.assertIn("canonical_moj_prop_policy_mismatch", self.review().blockers)

    def test_wrong_daily_loss_rule_fails_review_even_if_all_bool_flags_true(self):
        import prop_firm.policy_integrity as integrity
        with patch.object(integrity, "POLICY", replace(POLICY, max_daily_loss_pct=Decimal("5"))):
            self.assertIn("daily_loss_4pct", policy_drift_defects())
            self.assertFalse(self.review().eligible_for_external_legal_review)

    def test_one_stage_or_wrong_second_stage_cannot_be_governed_policy(self):
        import prop_firm.policy_integrity as integrity
        with patch.object(integrity, "POLICY", replace(POLICY, phase_two_goal_pct=Decimal("10"))):
            self.assertIn("two_stage_targets", policy_drift_defects())
            self.assertIn("canonical_moj_prop_policy_mismatch", self.review().blockers)

    def test_fifty_closed_positions_requirement_cannot_silently_disappear(self):
        import prop_firm.policy_integrity as integrity
        with patch.object(integrity, "POLICY", replace(POLICY, min_closed_trades_per_challenge=0)):
            self.assertIn("fifty_verified_closures", policy_drift_defects())
            self.assertFalse(self.review().eligible_for_external_legal_review)

    def test_any_proposed_plan_checkout_flag_blocks_governance_gate(self):
        import prop_firm.policy_integrity as integrity
        shadow = list(CHALLENGE_PLANS)
        shadow[0] = replace(shadow[0], checkout_enabled=True)
        with patch.object(integrity, "CHALLENGE_PLANS", tuple(shadow)):
            self.assertIn("payments_and_orders_not_enabled", policy_drift_defects())
            self.assertIn("canonical_moj_prop_policy_mismatch", self.review().blockers)

    def test_plan_one_is_owner_declared_not_external_funding_proof(self):
        report = policy_integrity_report()
        self.assertFalse(report["external_funding_or_broker_verified"])
        self.assertFalse(report["payment_or_trading_authorized"])
        self.assertEqual(self.review().checkout_enabled, False)
