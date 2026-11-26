"""No-network contract checks for the isolated price decision core."""
import unittest

from prop_firm.versioned_invoice_pricing import (
    FAILED_RETRY_FEE_SUN, FIRST_FEE_SUN, PurchaseClass,
    PriceDecisionRejected, decide_price, exact_settlement_amount,
)


class VersionedInvoicePricingTests(unittest.TestCase):
    def test_first_purchase_exact_amount(self):
        result = decide_price(sku="mojprop-starter30", purchase_class=PurchaseClass.FIRST)
        self.assertEqual(result.amount_sun, 30_000_000)
        self.assertEqual(result.currency, "TRX")
        self.assertTrue(result.price_version)

    def test_eligible_retry_exact_amount(self):
        result = decide_price(sku="mojprop-starter30",
                              purchase_class=PurchaseClass.FAILED_RETRY,
                              eligible_failed_retry=True)
        self.assertEqual(result.amount_sun, 18_000_000)

    def test_retry_without_eligibility_is_denied(self):
        with self.assertRaises(PriceDecisionRejected):
            decide_price(sku="mojprop-starter30",
                         purchase_class=PurchaseClass.FAILED_RETRY)

    def test_client_string_purchase_class_is_denied(self):
        with self.assertRaises(PriceDecisionRejected):
            decide_price(sku="mojprop-starter30", purchase_class="failed_retry",
                         eligible_failed_retry=True)

    def test_unapproved_sku_is_denied(self):
        with self.assertRaises(PriceDecisionRejected):
            decide_price(sku="another-plan", purchase_class=PurchaseClass.FIRST)

    def test_exact_invoice_amount_not_global_price(self):
        self.assertTrue(exact_settlement_amount(
            invoice_amount_sun=FAILED_RETRY_FEE_SUN,
            transfer_amount_sun=FAILED_RETRY_FEE_SUN))
        self.assertFalse(exact_settlement_amount(
            invoice_amount_sun=FAILED_RETRY_FEE_SUN,
            transfer_amount_sun=FIRST_FEE_SUN))
        self.assertFalse(exact_settlement_amount(
            invoice_amount_sun=FIRST_FEE_SUN,
            transfer_amount_sun=FAILED_RETRY_FEE_SUN))

    def test_bool_and_invalid_amount_denied(self):
        self.assertFalse(exact_settlement_amount(invoice_amount_sun=True,
                                                transfer_amount_sun=1))
        self.assertFalse(exact_settlement_amount(invoice_amount_sun=7,
                                                transfer_amount_sun=7))


if __name__ == "__main__":
    unittest.main()
