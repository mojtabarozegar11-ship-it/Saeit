"""Multi-tenant company master-account capacity checks; no broker orders."""
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from dataclasses import replace

from prop_firm.plan1_v141_shared_company_master_review import (
    VirtualTraderIntent, CompanyMasterSnapshot,
    CompanyMasterReviewRejected, review_company_master_capacity,
)


def snap(**kwargs):
    x=dict(company_broker_ref="COMPANY-LITE-MASTER-01",
           account_equity_usd="100",free_margin_usd="95",
           existing_risk_at_stop_usd="0",
           reserved_pending_risk_usd="0",
           position_accounting_mode="hedging")
    x.update(kwargs)
    return CompanyMasterSnapshot(**x)


def intent(num=1,**kwargs):
    x=dict(virtual_trader_ref=f"TRADER-{num}",
           virtual_challenge_ref=f"CHALLENGE-{num}",
           internal_order_ref=f"ORDER-{num}",
           symbol="XAUUSD",side="BUY",
           estimated_stop_risk_usd="1",
           estimated_margin_usd="1")
    x.update(kwargs)
    return VirtualTraderIntent(**x)


def review(*orders, state=None):
    return review_company_master_capacity(
        snapshot=snap() if state is None else state, intents=tuple(orders))


class CompanyMasterAccountTests(unittest.TestCase):
    def test_01_one_broker_account_two_site_traders(self):
        d=review(intent(1),intent(2))
        self.assertEqual(d.website_virtual_trader_count,2)
        self.assertEqual(d.company_broker_account_count,1)

    def test_02_hundred_traders_can_have_distinct_virtual_challenges(self):
        d=review(*(intent(i,estimated_stop_risk_usd="0.01",
                            estimated_margin_usd="0.01") for i in range(1,101)))
        self.assertEqual(d.website_virtual_trader_count,100)
        self.assertEqual(d.distinct_virtual_challenge_count,100)
        self.assertEqual(d.company_broker_account_count,1)
        self.assertTrue(d.capacity_math_within_limits)

    def test_03_hundred_traders_cannot_all_mirror_3_dollar_risk_on_100_dollars(self):
        d=review(*(intent(i,estimated_stop_risk_usd="3",
                            estimated_margin_usd="0.01") for i in range(1,101)))
        self.assertFalse(d.capacity_math_within_limits)
        self.assertEqual(d.aggregate_requested_risk_usd,Decimal("300"))
        self.assertIn("shared_company_account_aggregate_stop_risk_over_8_usd",d.reasons)

    def test_04_100_virtual_challenges_do_not_imply_100_broker_logins(self):
        d=review(*(intent(i,estimated_stop_risk_usd="0.01",
                            estimated_margin_usd="0.01") for i in range(1,101)))
        self.assertFalse(d.direct_trader_broker_login_needed)
        self.assertFalse(d.each_trader_has_independent_broker_account)

    def test_05_no_third_party_broker_deposits(self):
        self.assertFalse(review(intent()).third_party_broker_deposits_needed)

    def test_06_even_math_green_never_allows_live_routing(self):
        d=review(intent())
        self.assertTrue(d.capacity_math_within_limits)
        self.assertFalse(d.live_order_routing_authorized)
        self.assertFalse(d.broker_multitenant_routing_contractually_authorized)

    def test_07_no_payment_or_payout_authorized(self):
        d=review(intent())
        self.assertFalse(d.paid_enrollment_authorized)
        self.assertFalse(d.payout_authorized)

    def test_08_netted_opposite_site_trader_orders_are_not_isolated_positions(self):
        d=review(intent(1,side="BUY"),intent(2,side="SELL"),
                 state=snap(position_accounting_mode="netting"))
        self.assertIn("opposite_user_orders_need_independent_netting_attribution",d.reasons)
        self.assertFalse(d.capacity_math_within_limits)

    def test_09_hedging_math_can_handle_opposite_intents_but_does_not_execute(self):
        d=review(intent(1,side="BUY"),intent(2,side="SELL"))
        self.assertTrue(d.capacity_math_within_limits)
        self.assertFalse(d.live_order_routing_authorized)

    def test_10_single_risk_above_three_dollars_rejected(self):
        d=review(intent(1,estimated_stop_risk_usd="3.01"))
        self.assertIn("company_master_single_order_risk_over_3_usd",d.reasons)

    def test_11_exact_three_dollar_single_order_permitted_by_math(self):
        d=review(intent(1,estimated_stop_risk_usd="3"))
        self.assertTrue(d.capacity_math_within_limits)

    def test_12_total_exactly_eight_dollars_is_math_limit(self):
        d=review(intent(1,estimated_stop_risk_usd="3"),
                 intent(2,estimated_stop_risk_usd="3"),
                 intent(3,estimated_stop_risk_usd="2"))
        self.assertTrue(d.capacity_math_within_limits)
        self.assertEqual(d.remaining_aggregate_risk_usd,Decimal("0"))

    def test_13_total_over_eight_dollars_rejected(self):
        d=review(*(intent(i,estimated_stop_risk_usd="3") for i in range(1,4)))
        self.assertIn("shared_company_account_aggregate_stop_risk_over_8_usd",d.reasons)

    def test_14_existing_company_open_risk_counts_towards_global_cap(self):
        d=review(intent(),state=snap(existing_risk_at_stop_usd="7.5"))
        self.assertFalse(d.capacity_math_within_limits)

    def test_15_pending_orders_also_reserve_global_risk(self):
        d=review(intent(),state=snap(reserved_pending_risk_usd="7.5"))
        self.assertFalse(d.capacity_math_within_limits)

    def test_16_insufficient_margin_rejected(self):
        d=review(intent(1,estimated_margin_usd="10"),
                 state=snap(free_margin_usd="9"))
        self.assertIn("company_master_margin_insufficient",d.reasons)

    def test_17_no_stock_for_xauusd_only_draft(self):
        with self.assertRaises(CompanyMasterReviewRejected):
            review(intent(symbol="EURUSD"))

    def test_18_no_unreviewed_symbol_direction(self):
        with self.assertRaises(CompanyMasterReviewRejected):
            review(intent(side="HOLD"))

    def test_19_duplicate_order_ref_across_traders_rejected(self):
        with self.assertRaises(CompanyMasterReviewRejected):
            review(intent(1),intent(2,internal_order_ref="ORDER-1"))

    def test_20_cross_trader_same_virtual_challenge_rejected(self):
        with self.assertRaises(CompanyMasterReviewRejected):
            review(intent(1),intent(2,virtual_challenge_ref="CHALLENGE-1"))

    def test_21_same_trader_can_have_multiple_distinct_challenges(self):
        d=review(intent(1),intent(2,virtual_trader_ref="TRADER-1"))
        self.assertEqual(d.website_virtual_trader_count,1)
        self.assertEqual(d.distinct_virtual_challenge_count,2)

    def test_22_empty_batch_cannot_be_math_approved(self):
        d=review()
        self.assertFalse(d.capacity_math_within_limits)

    def test_23_bad_company_account_reference_rejected(self):
        with self.assertRaises(CompanyMasterReviewRejected):
            review(intent(),state=snap(company_broker_ref=""))

    def test_24_unknown_accounting_mode_rejected(self):
        with self.assertRaises(CompanyMasterReviewRejected):
            review(intent(),state=snap(position_accounting_mode="unknown"))

    def test_25_trader_cannot_supply_float_risk(self):
        with self.assertRaises(CompanyMasterReviewRejected):
            review(intent(estimated_stop_risk_usd=1.0))

    def test_26_nonfinite_risk_rejected(self):
        with self.assertRaises(CompanyMasterReviewRejected):
            review(intent(estimated_stop_risk_usd="NaN"))

    def test_27_negative_pending_risk_rejected(self):
        with self.assertRaises(CompanyMasterReviewRejected):
            review(intent(),state=snap(reserved_pending_risk_usd="-1"))

    def test_28_100_usd_risk_policy_cannot_be_used_for_unknown_equity(self):
        d=review(intent(),state=snap(account_equity_usd="150"))
        self.assertFalse(d.capacity_math_within_limits)
        self.assertIn("100_usd_master_account_risk_policy_requires_re_review",d.reasons)

    def test_29_reviewer_does_not_prove_broker_connection(self):
        d=review(intent())
        self.assertFalse(d.broker_api_connection_independently_verified)
        self.assertFalse(d.verified_live_broker_aggregate_state)

    def test_30_result_cannot_be_mutated_to_authorize_live_order(self):
        d=review(intent())
        with self.assertRaises(FrozenInstanceError):
            d.live_order_routing_authorized=True


if __name__=="__main__":
    unittest.main()
