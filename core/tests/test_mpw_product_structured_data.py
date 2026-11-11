"""Template-level SEO guard for the recovered MojPlayWin product page.

This tests repository source, not the live cPanel Passenger routing.
"""
import json
import re
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


class MojPlayWinProductStructuredDataTests(SimpleTestCase):
    def _render(self, pk, title, description):
        product = SimpleNamespace(pk=pk, title=title, description=description)
        return render_to_string("brands/mojplaywin/product.html", {"product": product})

    def test_three_public_products_use_own_canonical_and_jsonld_url(self):
        for pk in (72, 225, 879):
            with self.subTest(product_id=pk):
                html = self._render(pk, f"Product {pk}", "Private digital delivery")
                self.assertIn(
                    f'<link rel="canonical" href="https://mojplaywin.com/store/product/{pk}/">',
                    html,
                )
                self.assertIn('<meta name="robots" content="index,follow">', html)
                payloads = re.findall(
                    r'<script type="application/ld\+json">(.*?)</script>',
                    html,
                    flags=re.DOTALL,
                )
                self.assertEqual(len(payloads), 1)
                product_data = json.loads(payloads[0])
                self.assertEqual(product_data["@type"], "Product")
                self.assertEqual(product_data["name"], f"Product {pk}")
                self.assertEqual(product_data["url"], f"https://mojplaywin.com/store/product/{pk}/")
                self.assertEqual(product_data["brand"]["name"], "MojPlayWin")
                self.assertNotIn("offers", product_data)

    def test_markup_sensitive_product_text_is_json_safe(self):
        html = self._render(72, 'Chess "AI" & </script> Tips', "<b>Learn</b> & progress")
        payloads = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, flags=re.DOTALL)
        self.assertEqual(len(payloads), 1)
        data = json.loads(payloads[0])
        self.assertEqual(data["name"], 'Chess "AI" & </script> Tips')
        self.assertEqual(data["description"], "Learn & progress")
        self.assertNotIn('</script> Tips', payloads[0])
