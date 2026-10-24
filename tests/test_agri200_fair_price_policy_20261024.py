"""Independent assertions: USD 100, IRR 100, no autonomous discounts or sales."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "agri200_fair_price_policy", ROOT / "scripts/agri200_fair_pricing_owner_only_20261024.py"
)
assert SPEC and SPEC.loader
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


class OwnerOnlyFairPriceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.batch = P.build_priced_drafts(ROOT / "docs/agri200_p0_catalog.tsv")
        cls.products = cls.batch["products"]

    def test_two_stores_exact_unique_ids_and_expected_currencies(self):
        self.assertEqual(len(self.products), 200)
        self.assertEqual(len({p["product_id"] for p in self.products}), 200)
        self.assertEqual(self.batch["customer_purchasable_count"], 0)
        for index, product in enumerate(self.products, 1):
            if index <= 100:
                self.assertEqual(product["storefront"], "mojplaywin.com")
                self.assertEqual(product["currency"], "USD")
                self.assertRegex(product["suggested_base_price"]["amount"], r"^\\d+\\.\\d{2}$")
            else:
                self.assertEqual(product["storefront"], "zomorodmelal.ir")
                self.assertEqual(product["currency"], "IRR")
                self.assertRegex(product["suggested_base_price"]["amount"], r"^\\d+$")
            self.assertEqual(product["suggested_base_price"]["currency"], product["currency"])

    def test_prices_in_fair_curated_bands(self):
        for product in self.products:
            self.assertIn(product["suggested_base_price"]["amount"], P.PRICE_TABLE[product["currency"]].values())
            self.assertTrue(product["suggested_base_price"]["conditional_on_real_qc1000_and_checkout"])
        self.assertEqual(self.products[0]["suggested_base_price"]["amount"], "4.99")
        self.assertEqual(self.products[99]["suggested_base_price"]["amount"], "11.99")
        self.assertEqual(self.products[100]["suggested_base_price"]["amount"], "6" + "90000")
        self.assertEqual(self.products[-1]["suggested_base_price"]["amount"], "990000")

    def test_owner_alone_controls_discount_and_no_campaign(self):
        for product in self.products:
            policy = product["discount_policy"]
            self.assertEqual(policy["authority"], "OWNER_ONLY")
            self.assertEqual(policy["discount_percent"], 0)
            self.assertIsNone(policy["owner_authorization_record"])
            self.assertIs(policy["automatic_promotions_allowed"], False)
            self.assertIs(policy["auto_coupon_allowed"], False)
            self.assertIs(policy["discount_displayed"], False)
            self.assertIs(product["public_listing_enabled"], False)
            self.assertIs(product["sales_enabled"], False)
            self.assertIs(product["qc1000_approved"], False)
        self.assertEqual(P.quote_list_price("4.99"), "4.99")
        for value in (1, 5, 10, -1, 100, True, "10"):
            with self.assertRaises(P.OwnerDiscountRequired):
                P.quote_list_price("4.99", discount_percent=value)

    def test_price_must_not_be_treated_as_checkout_minors(self):
        self.assertEqual(self.products[0]["suggested_base_price"]["unit"], "USD_DOLLARS")
        self.assertEqual(self.products[100]["suggested_base_price"]["unit"], "IRANIAN_RIALS")
        self.assertIsNone(self.products[0]["price_minor_units"])
        self.assertIsNone(self.products[100]["price_minor_units"])
        self.assertEqual(self.products[0]["publication_state"], "PRIVATE_AWAITING_REAL_QC_PRICE_AND_CHECKOUT")


if __name__ == "__main__":
    unittest.main()
