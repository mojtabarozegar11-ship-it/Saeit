"""Reproduce owner-account risk checks without Django, broker or network."""
from dataclasses import replace
from decimal import Decimal as D
import unittest
from prop_firm.plan1_shared_owner_risk import (
    Compartment, REQUIRED_EVIDENCE, preview_owner_account_order,
)


class SharedOwnerRiskTests(unittest.TestCase):
    def setUp(self):
        self.a = Compartment("TRADER_A", 0, D("100"), D("100"), D("0.1"))
        self.b = Compartment("TRADER_B", 0, D("100"), D("100"), D("0.2"))
        self.kw = dict(compartments=(self.a,self.b),
            authenticated_trader_ref="TRADER_A", requested_trader_ref="TRADER_A",
            verified_owner_capital_usd=D("200"), broker_equity_usd=D("200"),
            broker_day_open_equity_usd=D("200"), broker_free_margin_usd=D("30"),
            other_account_open_and_reserved_risk_usd=D("0.1"),
            proposed_all_in_stop_risk_usd=D("0.8"), proposed_margin_usd=D("10"),
            evidence=dict.fromkeys(REQUIRED_EVIDENCE,True))

    def run_preview(self, **changes):
        return preview_owner_account_order(**(self.kw | changes))

    def test_valid_review_never_authorizes_or_executes(self):
        p = self.run_preview()
        self.assertTrue(p.review_allowed)
        self.assertEqual(p.allocated_capital_usd,D("200"))
        self.assertEqual(p.aggregate_open_and_reserved_risk_usd,D("0.4"))
        self.assertEqual(p.trader_order_limit_usd,D("0.8"))
        self.assertEqual(p.trader_aggregate_limit_usd,D("1.6"))
        self.assertEqual(p.account_aggregate_limit_usd,D("3.2"))
        self.assertFalse(p.broker_order_authorized)
        self.assertFalse(p.capital_reserved)
        self.assertFalse(p.order_submitted)

    def test_every_missing_independent_gate_blocks(self):
        for key in REQUIRED_EVIDENCE:
            with self.subTest(key=key):
                e=self.kw["evidence"] | {key:False}
                self.assertIn(key,self.run_preview(evidence=e).reasons)

    def test_boolean_impostor_rejected(self):
        e=self.kw["evidence"] | {REQUIRED_EVIDENCE[0]:1}
        self.assertFalse(self.run_preview(evidence=e).review_allowed)

    def test_missing_evidence_key_rejected(self):
        with self.assertRaises(ValueError):
            self.run_preview(evidence={})

    def test_cross_trader_blocked(self):
        self.assertIn("cross_trader_request",
                      self.run_preview(requested_trader_ref="TRADER_B").reasons)

    def test_missing_trader_blocked(self):
        self.assertIn("trader_allocation_missing",
                      self.run_preview(compartments=(self.b,)).reasons)

    def test_duplicate_trader_rejected(self):
        with self.assertRaises(ValueError):
            self.run_preview(compartments=(self.a,self.a))

    def test_overallocation_blocked(self):
        self.assertIn("owner_capital_overallocated",
                      self.run_preview(verified_owner_capital_usd=D("199")).reasons)

    def test_real_equity_cannot_be_overallocated(self):
        self.assertIn("owner_capital_overallocated",
                      self.run_preview(broker_equity_usd=D("199")).reasons)

    def test_single_order_limit_exact_boundary(self):
        self.assertTrue(self.run_preview().review_allowed)
        self.assertIn("trader_single_order_limit",
                      self.run_preview(proposed_all_in_stop_risk_usd=D("0.8001")).reasons)

    def test_pending_exposure_counts_against_trader(self):
        a=replace(self.a,open_and_reserved_risk_usd=D("0.81"))
        self.assertIn("trader_aggregate_risk_limit",
                      self.run_preview(compartments=(a,self.b)).reasons)

    def test_nonprogram_exposure_counts_against_shared_account(self):
        self.assertIn("owner_account_aggregate_risk_limit",
                      self.run_preview(other_account_open_and_reserved_risk_usd=D("2.11")).reasons)

    def test_daily_loss_floor_blocks(self):
        a=replace(self.a,equity_usd=D("96"))
        self.assertIn("trader_daily_loss_floor_reached",
                      self.run_preview(compartments=(a,self.b)).reasons)

    def test_projected_loss_floor_blocks(self):
        a=replace(self.a,equity_usd=D("96.9"))
        self.assertIn("trader_projected_loss_floor_reached",
                      self.run_preview(compartments=(a,self.b)).reasons)

    def test_shared_projected_floor_blocks(self):
        self.assertIn("account_projected_loss_floor_reached",
            self.run_preview(broker_day_open_equity_usd=D("207")).reasons)

    def test_margin_limit(self):
        self.assertIn("broker_free_margin_insufficient",
                      self.run_preview(broker_free_margin_usd=D("9.99")).reasons)

    def test_invalid_risk_amounts(self):
        for x in (D("NaN"),D("Infinity"),D("-1"),D("0"),True,0.8,D("0.000000001")):
            with self.subTest(x=x),self.assertRaises(ValueError):
                self.run_preview(proposed_all_in_stop_risk_usd=x)

    def test_invalid_tier(self):
        for tier in (-1,14,True):
            with self.subTest(tier=tier),self.assertRaises(ValueError):
                self.run_preview(compartments=(replace(self.a,tier_index=tier),self.b))


if __name__ == "__main__":
    unittest.main()
