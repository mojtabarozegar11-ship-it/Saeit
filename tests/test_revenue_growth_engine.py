import unittest

from core.economic_master_agent import EconomicMasterAgent
from core.revenue_growth_engine import prioritize_revenue_growth


def snapshot(**changes):
    baseline = {
        "sellable_offers": 1,
        "qualified_leads": 1,
        "paid_orders": 1,
        "delivered_orders": 1,
        "checkout_verified": True,
        "delivery_verified": True,
        "settlement_evidence_verified": True,
        "settled_revenue": "800",
        "operating_costs": "300",
        "committed_costs": "100",
        "protected_reserve": "150",
    }
    baseline.update(changes)
    return baseline


class RevenueGrowthEngineTests(unittest.TestCase):
    def test_paid_unfulfilled_orders_win_over_new_sales(self):
        result = prioritize_revenue_growth(snapshot(paid_orders=3, delivered_orders=1))
        self.assertEqual(result["next_action"], "fulfill_paid_orders")

    def test_failed_checkout_blocks_acquisition(self):
        result = prioritize_revenue_growth(snapshot(checkout_verified=False))
        self.assertEqual(result["next_action"], "repair_and_verify_checkout")

    def test_no_sellable_offer_precedes_lead_generation(self):
        result = prioritize_revenue_growth(snapshot(sellable_offers=0))
        self.assertEqual(result["next_action"], "complete_sellable_offer")
        self.assertTrue(result["external_write_requires_owner_approval"])

    def test_delivery_path_failure_takes_precedence(self):
        result = prioritize_revenue_growth(snapshot(delivery_verified=False))
        self.assertEqual(result["next_action"], "repair_and_verify_delivery")

    def test_internal_paid_orders_do_not_count_as_revenue(self):
        result = prioritize_revenue_growth(snapshot(settlement_evidence_verified=False))
        self.assertEqual(result["next_action"], "reconcile_settled_receipts")
        self.assertIsNone(result["metrics"]["settled_revenue"])

    def test_unproven_receipt_cannot_claim_profit_even_with_large_input(self):
        result = prioritize_revenue_growth(snapshot(
            paid_orders=0, delivered_orders=0, settlement_evidence_verified=False,
            settled_revenue="100000000",
        ))
        self.assertIsNone(result["metrics"]["operating_surplus_after_commitments_and_reserve"])

    def test_cannot_hide_unknown_costs_behind_large_revenue(self):
        result = prioritize_revenue_growth(snapshot(operating_costs=None))
        self.assertEqual(result["next_action"], "reconcile_operating_cashflow")
        self.assertFalse(result["metrics"]["cost_coverage_verified"])

    def test_qualified_leads_without_payments_get_conversion_priority(self):
        result = prioritize_revenue_growth(snapshot(
            paid_orders=0, delivered_orders=0, qualified_leads=10,
        ))
        self.assertEqual(result["next_action"], "improve_lead_to_purchase_conversion")

    def test_zero_qualified_leads_get_acquisition_priority(self):
        result = prioritize_revenue_growth(snapshot(qualified_leads=0))
        self.assertEqual(result["next_action"], "prepare_qualified_customer_acquisition")
        self.assertTrue(result["external_write_requires_owner_approval"])

    def test_verified_receipts_insufficient_for_self_funding(self):
        result = prioritize_revenue_growth(snapshot(settled_revenue="520"))
        self.assertEqual(result["next_action"], "increase_net_cashflow_before_expansion")
        self.assertEqual(result["metrics"]["operating_surplus_after_commitments_and_reserve"], "-30")

    def test_surplus_never_authorizes_purchase_or_deployment(self):
        result = EconomicMasterAgent().prioritize_revenue_growth(snapshot())
        self.assertEqual(result["next_action"], "scale_proven_offer_without_new_spend")
        self.assertTrue(result["metrics"]["cost_coverage_verified"])
        self.assertFalse(result["purchase_permitted"])
        self.assertFalse(result["deployment_permitted"])

    def test_boolean_or_negative_order_count_rejected(self):
        for value in (True, -1, "2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                prioritize_revenue_growth(snapshot(paid_orders=value))

    def test_delivery_cannot_exceed_paid_orders(self):
        with self.assertRaises(ValueError):
            prioritize_revenue_growth(snapshot(paid_orders=1, delivered_orders=2))

    def test_money_float_and_negative_are_not_trusted(self):
        for value in (10.4, "-10", "NaN", "infinite"):
            with self.subTest(value=value):
                result = prioritize_revenue_growth(snapshot(operating_costs=value))
                self.assertEqual(result["next_action"], "reconcile_operating_cashflow")


if __name__ == "__main__":
    unittest.main()
