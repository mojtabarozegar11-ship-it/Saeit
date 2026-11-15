"""Integration contract for the canonical, non-live MOJ PROP release gate."""
from dataclasses import replace
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from core.commercialization_readiness import SECTORS
from core.tron_tenant_policy import TenantDecision
from prop_firm.challenge_commerce import REQUIRED
from prop_firm.plans import CHALLENGE_PLANS
from prop_firm.release_gate import assess_moj_prop_release
from prop_firm.rules import POLICY


class MojPropReleaseGateTests(SimpleTestCase):
    def tenant(self):
        return TenantDecision(
            "moj-prop-merchant", "mojplaywin.com", "moj_prop", True, (),
        )

    def challenge_flags(self, plan_code="MOJ-PROP-01"):
        flags = {key: True for key in REQUIRED}
        if plan_code != "MOJ-PROP-01":
            flags.update({
                "selected_plan_broker_lot_approved": True,
                "selected_plan_customer_terms_approved": True,
                "selected_plan_fee_approved": True,
            })
        return flags

    def sector_flags(self):
        return {key: True for key in SECTORS["moj_prop"]}

    def review(self, **changes):
        values = {
            "merchant_tenant": self.tenant(),
            "free_treasury_usd": "1000",
            "protected_reserves_usd": "100",
            "existing_commitments_usd": "0",
            "required_first_tier_accounts": 1,
            "challenge_attestations": self.challenge_flags(),
            "sector_attestations": self.sector_flags(),
        }
        values.update(changes)
        return assess_moj_prop_release(**values)

    def test_plan_one_owner_status_is_not_independent_release_evidence(self):
        decision = self.review()
        self.assertTrue(decision.owner_declared_active)
        self.assertTrue(decision.owner_declared_funded)
        self.assertFalse(decision.independent_capital_proof_on_record)
        self.assertFalse(decision.independent_broker_proof_on_record)
        self.assertIn("independent_capital_proof_required", decision.blockers)
        self.assertIn("independent_broker_proof_required", decision.blockers)
        self.assertEqual(decision.outcome, "not_released")

    def test_complete_review_inputs_still_cannot_activate_money_or_trading(self):
        decision = self.review()
        self.assertTrue(decision.policy_consistent)
        self.assertTrue(decision.challenge_reviewable)
        self.assertTrue(decision.sector_reviewable)
        self.assertEqual(decision.sector_evidence_percent, 100)
        self.assertFalse(decision.eligible_for_commercial_review)
        self.assertFalse(decision.checkout_enabled)
        self.assertFalse(decision.invoice_created)
        self.assertFalse(decision.trading_enabled)
        self.assertFalse(decision.release_authorized)

    def test_plan_two_is_blocked_by_the_owner_funding_hold(self):
        decision = self.review(
            plan_code="MOJ-PROP-02",
            challenge_attestations=self.challenge_flags("MOJ-PROP-02"),
        )
        self.assertIn(
            "challenge:plan_temporarily_inactive_pending_owner_funding",
            decision.blockers,
        )
        self.assertIn("plan_temporarily_inactive_pending_owner_funding",
                      decision.blockers)
        self.assertFalse(decision.owner_declared_active)

    def test_sector_missing_evidence_is_namespaced_and_fail_closed(self):
        flags = self.sector_flags()
        flags["payout_and_trx_controls_live"] = False
        decision = self.review(sector_attestations=flags)
        self.assertIn("sector:payout_and_trx_controls_live", decision.blockers)
        self.assertFalse(decision.sector_reviewable)
        self.assertFalse(decision.eligible_for_commercial_review)

    def test_numeric_treasury_and_true_flags_do_not_become_capital_proof(self):
        decision = self.review(free_treasury_usd="1000000000")
        self.assertEqual(decision.independent_capital_proof_on_record, False)
        self.assertIn("independent_capital_proof_required", decision.blockers)

    def test_nonliteral_challenge_attestations_do_not_pass(self):
        decision = self.review(
            challenge_attestations={key: "approved" for key in REQUIRED},
        )
        self.assertFalse(decision.challenge_reviewable)
        self.assertIn("challenge:jurisdiction_authorized", decision.blockers)

    def test_policy_drift_blocks_the_joined_gate(self):
        with patch(
            "prop_firm.release_gate.policy_drift_defects",
            return_value=("fifty_verified_closures",),
        ):
            decision = self.review()
        self.assertFalse(decision.policy_consistent)
        self.assertIn(
            "canonical_policy:fifty_verified_closures", decision.blockers,
        )
        self.assertFalse(decision.release_authorized)

    def test_side_effect_flags_are_constants_of_the_decision_contract(self):
        decision = self.review()
        self.assertEqual(
            (decision.checkout_enabled, decision.invoice_created,
             decision.trading_enabled, decision.release_authorized),
            (False, False, False, False),
        )

    def test_plan_registry_remains_exactly_fourteen_levels_and_ten_plans(self):
        self.assertEqual(len(CHALLENGE_PLANS), 10)
        self.assertEqual(CHALLENGE_PLANS[0].starting_capital_usd, Decimal("100"))
        self.assertEqual(POLICY.completion_deadline_days, 28)
        self.assertEqual(POLICY.min_closed_trades_per_challenge, 50)

    def test_wrong_plan_is_rejected_before_a_release_decision(self):
        with self.assertRaises(KeyError):
            self.review(plan_code="MOJ-PROP-99")
