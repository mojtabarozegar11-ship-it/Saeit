"""Offline, read-only guard for the source-owned MojPlayWin product template.

These checks deliberately do not submit orders or imply that production is deployed.
"""
from pathlib import Path
import re
import unittest


TEMPLATE = Path(__file__).resolve().parents[1] / "core/templates/brands/mojplaywin/product.html"


class ProductTemplateSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = TEMPLATE.read_text(encoding="utf-8")

    def test_source_owned_template_is_complete(self):
        self.assertTrue(self.html.startswith("<!doctype html>"))
        self.assertIn('<html lang="en">', self.html)
        self.assertIn('<main id="product">', self.html)
        self.assertIn('<link rel="canonical"', self.html)
        self.assertIn("{{ product.title }}", self.html)

    def test_conditional_tags_are_balanced(self):
        stack = []
        for tag in re.findall(r"\{%\s*(if|elif|else|endif)\b[^%]*%\}", self.html):
            if tag == "if":
                stack.append(tag)
            elif tag in ("elif", "else"):
                self.assertTrue(stack, "orphaned alternative branch")
            elif tag == "endif":
                self.assertTrue(stack, "orphaned endif")
                stack.pop()
        self.assertFalse(stack, "unclosed conditional branch")

    def test_all_three_current_products_have_distinct_details(self):
        self.assertIn("product.pk == 72", self.html)
        self.assertIn("415 pages", self.html)
        self.assertIn("84-day", self.html)
        self.assertIn("product.pk == 225", self.html)
        self.assertIn("40 pages", self.html)
        self.assertIn("landscape PDF", self.html)
        self.assertIn("product.pk == 879", self.html)
        self.assertIn("five original SVG", self.html)
        self.assertIn("Demo photographs are", self.html)

    def test_prices_are_dynamic_and_currency_gated(self):
        self.assertIn('product.currency == "USD"', self.html)
        self.assertIn("product.price|floatformat:2", self.html)
        self.assertNotIn("US $7.50", self.html)
        self.assertNotIn("US $4.00", self.html)
        self.assertNotIn("US $6.80", self.html)

    def test_no_trial_or_unknown_product_checkout(self):
        # Buyer CTA is nested under the three-SKU allowlist and USD guard.
        start = self.html.index("{% if product.pk == 72 or product.pk == 225 or product.pk == 879 %}")
        end = self.html.index("{% endif %}", self.html.index('{% endif %}', start) + 1)
        guarded = self.html[start:end]
        self.assertIn('/commerce/book/{{ product.pk }}/', guarded)
        self.assertIn('product.currency == "USD"', guarded)
        self.assertNotIn('product.pk == 779', self.html)

    def test_buyer_security_and_recovery_copy_is_truthful(self):
        for phrase in (
            "valid purchase email", "exact native TRX amount", "TRON mainnet",
            "server-side blockchain verification", "not currently available",
            "Do not send USDT", "/terms/", "/privacy/", "/support/",
        ):
            self.assertIn(phrase, self.html)

    def test_no_client_side_script_or_payment_side_effect(self):
        self.assertNotIn("<script", self.html.lower())
        self.assertNotIn("<form", self.html.lower())
        self.assertNotIn("mailto:", self.html.lower())
        self.assertFalse(re.search(r'on(?:click|load|error)\s*=', self.html, re.I))


if __name__ == "__main__":
    unittest.main()
