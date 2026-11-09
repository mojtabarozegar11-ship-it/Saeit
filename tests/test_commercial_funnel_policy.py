import unittest

from core.commercial_funnel_policy import EVENT_NAMES, decide_funnel_followup


def evidence(**changes):
    counts = {name: 0 for name in EVENT_NAMES}
    counts.update(changes)
    return counts


class CommercialFunnelPolicyTests(unittest.TestCase):
    def test_failed_delivery_is_top_priority(self):
        result = decide_funnel_followup(evidence(delivery_failure=3, view_store=20), 1)
        self.assertEqual(result["next_diagnostic"], "inspect_delivery_failures")

    def test_payment_to_delivery_path_gets_review_not_claim(self):
        result = decide_funnel_followup(evidence(payment_confirmed=4), 1)
        self.assertEqual(result["next_diagnostic"], "inspect_payment_to_delivery_path")
        self.assertFalse(result["sales_settlement_verified"])

    def test_checkout_without_invoice(self):
        result = decide_funnel_followup(evidence(begin_checkout=5), 1)
        self.assertEqual(result["next_diagnostic"], "inspect_checkout_to_invoice_path")

    def test_invoice_without_payment(self):
        result = decide_funnel_followup(evidence(invoice_created=5), 1)
        self.assertEqual(result["next_diagnostic"], "inspect_invoice_to_payment_path")

    def test_no_sellable_offer(self):
        result = decide_funnel_followup(evidence(), 0)
        self.assertEqual(result["next_diagnostic"], "prepare_verified_sellable_offer")

    def test_no_recorded_views(self):
        result = decide_funnel_followup(evidence(), 2)
        self.assertEqual(result["next_diagnostic"], "prepare_free_customer_acquisition")

    def test_views_without_checkout(self):
        result = decide_funnel_followup(evidence(view_item=8), 2)
        self.assertEqual(result["next_diagnostic"], "inspect_product_to_checkout_path")

    def test_progress_never_counts_settled_revenue(self):
        result = decide_funnel_followup(evidence(
            view_store=12, begin_checkout=4, invoice_created=4,
            payment_confirmed=3, delivery_success=3,
        ), 2)
        self.assertEqual(result["next_diagnostic"], "inspect_external_settlement_and_fulfillment")
        self.assertFalse(result["sales_settlement_verified"])
        self.assertFalse(result["purchase_permitted"])

    def test_unknown_or_negative_counts_fail_closed(self):
        for value in (-1, True, None, "2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decide_funnel_followup(evidence(view_item=value), 1)

    def test_missing_any_metric_fails_closed(self):
        with self.assertRaises(ValueError):
            decide_funnel_followup({"view_store": 4}, 1)


if __name__ == "__main__":
    unittest.main()
