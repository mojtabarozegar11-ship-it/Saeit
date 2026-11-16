"""Offline regressions for real MOJ-PROP-01 funding obligation semantics.

Synthetic values only. This suite cannot prove a wallet balance, legal
permission, broker funding, paid customer, or live account allocation.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from prop_firm.funded_delivery_obligation import (
    PLAN_CODE, assess_funded_delivery,
)
from prop_firm.rules import LEVELS


class FundedDeliveryObligationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
        self.due = self.now + timedelta(days=2)
        self.args = dict(
            plan_code=PLAN_CODE,
            tier_index=0,
            challenge_pass_verified=True,
            promotion_verified=False,
            trading_rules_compliant=True,
            kyc_verified=True,
            signed_customer_contract_verified=True,
            independent_broker_account_verified=False,
            independent_funding_allocation_verified=False,
            assigned_capital_usd="0",
            contractual_delivery_due_at=self.due,
            now=self.now,
        )

    def assess(self, **overrides):
        data = {**self.args, **overrides}
        return assess_funded_delivery(**data)

    def test_initial_100_usd_promised_but_company_pending(self):
        result = self.assess()
        self.assertEqual(result.tier_capital_usd, Decimal("100"))
        self.assertEqual(result.final_tier_usd, Decimal("100000"))
        self.assertTrue(result.customer_conditions_verified)
        self.assertTrue(result.company_delivery_obligation)
        self.assertEqual(result.status, "company_funding_delivery_pending")
        self.assertFalse(result.delivery_independently_proven)

    def test_company_shortfall_does_not_mark_trader_as_failed(self):
        result = self.assess(now=self.due + timedelta(seconds=1))
        self.assertEqual(result.status, "company_funding_delivery_overdue")
        self.assertTrue(result.company_delivery_overdue)
        self.assertFalse(result.trader_failed_due_to_company_funding)
        self.assertTrue(result.company_delivery_obligation)

    def test_due_timestamp_boundary_is_not_overdue(self):
        self.assertFalse(self.assess(now=self.due).company_delivery_overdue)
        self.assertTrue(self.assess(
            now=self.due + timedelta(microseconds=1)
        ).company_delivery_overdue)

    def test_missing_contract_delivery_deadline_is_explicit_merchant_gap(self):
        result = self.assess(contractual_delivery_due_at=None)
        self.assertEqual(result.status, "company_contract_delivery_deadline_missing")
        self.assertTrue(result.company_delivery_obligation)
        self.assertFalse(result.company_delivery_overdue)

    def test_owner_balance_claim_never_counts_as_allocated_funded_account(self):
        # Even a claimed USD 1m cannot prove a broker account is funded.
        result = self.assess(assigned_capital_usd="1000000")
        self.assertFalse(result.delivery_independently_proven)
        self.assertTrue(result.company_delivery_obligation)

    def test_broker_proof_without_actual_allocation_is_not_delivery(self):
        result = self.assess(independent_broker_account_verified=True)
        self.assertFalse(result.delivery_independently_proven)

    def test_allocation_proof_without_broker_access_is_not_delivery(self):
        result = self.assess(independent_funding_allocation_verified=True,
                             assigned_capital_usd="100")
        self.assertFalse(result.delivery_independently_proven)

    def test_exact_tier_amount_with_both_proofs_is_delivery(self):
        result = self.assess(independent_broker_account_verified=True,
                             independent_funding_allocation_verified=True,
                             assigned_capital_usd=Decimal("100"))
        self.assertTrue(result.delivery_independently_proven)
        self.assertEqual(result.status, "funding_delivered_with_independent_evidence")
        self.assertFalse(result.company_delivery_overdue)

    def test_partial_allocation_is_never_full_funding(self):
        result = self.assess(independent_broker_account_verified=True,
                             independent_funding_allocation_verified=True,
                             assigned_capital_usd="99.99")
        self.assertFalse(result.delivery_independently_proven)

    def test_higher_level_requires_verified_promotion(self):
        result = self.assess(tier_index=1, assigned_capital_usd="200")
        self.assertFalse(result.customer_conditions_verified)
        self.assertIn("promotion_milestone_not_verified", result.reasons)
        self.assertEqual(result.status, "awaiting_customer_qualification_evidence")
        self.assertFalse(result.company_delivery_obligation)

    def test_qualifying_higher_level_creates_company_duty(self):
        result = self.assess(tier_index=1, promotion_verified=True,
                             now=self.due + timedelta(days=1))
        self.assertTrue(result.customer_conditions_verified)
        self.assertEqual(result.tier_capital_usd, Decimal("200"))
        self.assertTrue(result.company_delivery_overdue)

    def test_top_tier_continues_without_auto_expiry(self):
        result = self.assess(tier_index=13, promotion_verified=True,
                             independent_broker_account_verified=True,
                             independent_funding_allocation_verified=True,
                             assigned_capital_usd="100000",
                             now=self.due + timedelta(days=365))
        self.assertTrue(result.delivery_independently_proven)
        self.assertFalse(result.funded_account_auto_expires_after_challenge)
        self.assertEqual(result.tier_capital_usd, LEVELS[-1])

    def test_all_14_tier_promises_match_canonical_rules(self):
        for i, capital in enumerate(LEVELS):
            with self.subTest(level=i+1):
                result = self.assess(tier_index=i,
                                     promotion_verified=True if i else False)
                self.assertEqual(result.tier_capital_usd, capital)
                self.assertFalse(result.checkout_authorized)
                self.assertFalse(result.capital_transfer_authorized)

    def test_missing_customer_conditions_are_not_merchant_financial_failure(self):
        for key in ("challenge_pass_verified", "trading_rules_compliant",
                    "kyc_verified", "signed_customer_contract_verified"):
            with self.subTest(key=key):
                result = self.assess(**{key: False}, now=self.due+timedelta(days=1))
                self.assertFalse(result.company_delivery_obligation)
                self.assertFalse(result.company_delivery_overdue)
                self.assertFalse(result.trader_failed_due_to_company_funding)

    def test_truthy_strings_cannot_spoof_independent_proof(self):
        for key in ("challenge_pass_verified", "promotion_verified",
                    "trading_rules_compliant", "kyc_verified",
                    "signed_customer_contract_verified",
                    "independent_broker_account_verified",
                    "independent_funding_allocation_verified"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.assess(**{key: "true"})

    def test_invalid_plan_and_tier_rejected(self):
        for plan in ("MOJPROP-STARTER30", "MOJ-PROP-02", "", None, True):
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                self.assess(plan_code=plan)
        for tier in (-1, 14, 1.0, True, False, "0", None):
            with self.subTest(tier=tier), self.assertRaises(ValueError):
                self.assess(tier_index=tier)

    def test_malformed_amount_cannot_approve_delivery(self):
        for amount in (True, False, None, float("nan"), 1.0, "-1",
                       "NaN", "Infinity", "not-a-number", [], {}):
            with self.subTest(amount=repr(amount)), self.assertRaises(ValueError):
                self.assess(assigned_capital_usd=amount)

    def test_aware_dates_required_and_offsets_normalized(self):
        with self.assertRaises(ValueError):
            self.assess(now=self.now.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            self.assess(contractual_delivery_due_at=self.due.replace(tzinfo=None))
        local = timezone(timedelta(hours=3))
        same_time = self.due.astimezone(local)
        result = self.assess(contractual_delivery_due_at=same_time, now=self.due)
        self.assertFalse(result.company_delivery_overdue)

    def test_never_grants_payment_or_broker_actions(self):
        result = self.assess(independent_broker_account_verified=True,
                             independent_funding_allocation_verified=True,
                             assigned_capital_usd="100")
        self.assertFalse(result.checkout_authorized)
        self.assertFalse(result.capital_transfer_authorized)
        self.assertFalse(result.trader_failed_due_to_company_funding)


if __name__ == "__main__":
    unittest.main()
