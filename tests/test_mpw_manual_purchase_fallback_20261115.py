"""A manual purchase inquiry must stay available beside each dynamic checkout.

Pure store-template contract. Does not imply an issued invoice or payment.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import unittest


ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "core/templates/mojplaywin/store.html"


class AnchorLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.append(dict(attrs).get("href", ""))


class StoreFallbackTests(unittest.TestCase):
    def setUp(self):
        self.template = STORE.read_text(encoding="utf-8")
        parser = AnchorLinks()
        parser.feed(self.template)
        self.hrefs = parser.hrefs

    def test_all_three_paid_products_have_nonpaying_inquiry_route(self):
        for sku in (72, 225, 879):
            with self.subTest(sku=sku):
                expected = f"/moj-prop/?service=digital&product={sku}#request"
                self.assertIn(expected, self.hrefs)
                parsed = urlsplit(expected)
                self.assertEqual(parsed.path, "/moj-prop/")
                self.assertEqual(parsed.fragment, "request")
                self.assertEqual(parse_qs(parsed.query)["product"], [str(sku)])

    def test_existing_buy_and_detail_routes_are_not_destroyed(self):
        for sku in (72, 225):
            self.assertIn(f"/store/product/{sku}/checkout/", self.hrefs)
        self.assertIn("/store/product/879/", self.hrefs)

    def test_fallback_must_not_pretend_payment_occured(self):
        self.assertIn("A request creates no payment obligation", self.template)
        self.assertIn("never transfer funds without a verified invoice", self.template)
        self.assertIn("manual purchase", self.template.lower())
