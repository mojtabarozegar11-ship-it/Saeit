"""Offline storefront contract: product checkout controls stay in layout flow.

This guards the three-card product template against the prior single-row flex
layout, where three non-wrapping children could be clipped on narrow screens.
It does not claim a browser or production visual verification.
"""
from html.parser import HTMLParser
from pathlib import Path
import unittest


STORE = Path(__file__).resolve().parents[1] / "core/templates/mojplaywin/store.html"


class _ProductLinks(HTMLParser):
    VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.links = []
        self.products = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if self.depth:
            if tag not in self.VOID:
                self.depth += 1
            if tag == "a":
                self.products[-1].append(data.get("href", ""))
        elif tag == "article" and "mpw-product" in data.get("class", "").split():
            self.products.append([])
            self.depth = 1

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1


class StoreMobileCheckoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = STORE.read_text(encoding="utf-8")

    def test_three_featured_products_keep_purchase_and_details_links(self):
        parser = _ProductLinks()
        parser.feed(self.source)
        self.assertEqual(len(parser.products), 3)
        for links, sku in zip(parser.products, (72, 225, 879)):
            self.assertEqual(links.count(f"/commerce/book/{sku}/"), 1)
            self.assertEqual(links.count(f"/store/product/{sku}/"), 1)

    def test_cta_group_no_longer_uses_clipped_nonwrapping_flex_row(self):
        css = self.source.split('<style id="mpw-store-catalog-20261026">', 1)[1].split(
            "</style>", 1
        )[0]
        checkout_rule = css.split("/* Match the live storefront: wrapping keeps", 1)[1].split(
            ".mpw-product-bottom{", 1
        )[1].split("}", 1)[0]
        self.assertIn("flex-wrap:wrap", checkout_rule)

    def test_checkout_copy_requires_email_and_discloses_no_cross_device_recovery(self):
        self.assertIn("a valid purchase email must be entered", self.source)
        self.assertIn("Email receipts and recovery on another device are not yet available", self.source)

    def test_checkout_guide_is_single_column_on_mobile(self):
        self.assertIn(".mpw-checkout-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))", self.source)
        self.assertIn("@media(max-width:650px){.mpw-checkout-steps{grid-template-columns:1fr}}", self.source)


if __name__ == "__main__":
    unittest.main()
