"""Buyer-facing catalog contracts; no checkout POST, network, mail or DB."""
from html.parser import HTMLParser
from pathlib import Path
import unittest


STORE = Path(__file__).resolve().parents[1] / "core/templates/mojplaywin/store.html"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.anchors.append(dict(attrs))


class StorefrontTruth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = STORE.read_text("utf-8")
        parser = Links()
        parser.feed(cls.source)
        cls.links = [item.get("href", "") for item in parser.anchors]

    def test_each_featured_product_uses_live_guest_trx_checkout(self):
        for product_id in (72, 225, 879):
            with self.subTest(product_id=product_id):
                self.assertEqual(self.links.count(f"/commerce/book/{product_id}/"), 1)
                self.assertEqual(self.links.count(f"/store/product/{product_id}/"), 1)
                self.assertNotIn(f"/store/product/{product_id}/checkout/", self.links)

    def test_three_featured_are_not_misrepresented_as_entire_catalog(self):
        self.assertIn("3 featured products", self.source)
        self.assertIn('"numberOfItems": 3', self.source)
        self.assertEqual(self.source.count('"@type": "ListItem"'), 3)
        self.assertEqual(self.links.count("/commerce/trx-easy/"), 1)
        self.assertNotIn("Explore three original digital products", self.source)

    def test_payment_and_recovery_claims_match_current_operation(self):
        self.assertIn("valid purchase email must be entered", self.source)
        self.assertIn("No account or wallet connection is required", self.source)
        self.assertIn("Email receipts and recovery on another device are not yet available", self.source)
        self.assertIn("in the original browser", self.source)
        self.assertEqual(self.links.count("/commerce/trx-easy/purchases/"), 1)
        self.assertNotIn("arrive by email", self.source)

    def test_three_plain_language_steps_never_promise_email_fulfillment(self):
        self.assertIn('<ol class="mpw-checkout-steps" aria-label="Three steps to purchase">', self.source)
        for step in ("1. Enter your email", "2. Pay the TRX invoice",
                     "3. Download in this browser"):
            self.assertEqual(self.source.count(step), 1)
        self.assertIn("After blockchain confirmation", self.source)
        self.assertIn("same browser to retrieve your file", self.source)
        self.assertNotIn("download link arrives by email", self.source)


if __name__ == "__main__":
    unittest.main()
