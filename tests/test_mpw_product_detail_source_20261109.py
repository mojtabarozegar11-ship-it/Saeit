"""Offline, read-only guard for the source-owned MojPlayWin product template.

These checks deliberately do not submit orders or imply that production is deployed.
"""
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace
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
        self.assertIn("five SVG illustrations", self.html)
        self.assertNotIn("five original SVG", self.html)
        self.assertNotIn("One-site/client usage license;", self.html)
        self.assertIn("not a verified license grant", self.html)
        self.assertIn("Demo photographs are", self.html)

    def test_product_specific_contents_and_original_browser_recovery(self):
        for phrase in (
            "Critical-position worksheets",
            "40 landscape-format pages",
            "no exact age band is claimed",
            "Project gallery and inquiry handoff",
            "arrange hosting, branding details",
            '/commerce/trx-easy/purchases/',
            "original browser session",
        ):
            self.assertIn(phrase, self.html)
        self.assertIn("Email receipts and cross-device email recovery are not currently available", self.html)

    def test_verified_preview_media_is_explicitly_not_paid_stock(self):
        self.assertIn('/static/site/mojplaywin-products/chess-improvement.webp', self.html)
        self.assertIn('/static/site/mojplaywin-products/taniya-baker-worms.webp', self.html)
        self.assertIn("Book cover artwork, not a preview of the paid PDF pages", self.html)
        self.assertIn("Storybook promotional artwork, not a sample of its 40 PDF pages", self.html)
        self.assertIn("/site-preview", self.html)
        self.assertIn('rel="noopener noreferrer"', self.html)
        self.assertIn('not</strong> the exact downloadable ZIP', self.html)
        self.assertIn("project planner, Studio Desk and WorldForge tools are not part of product 879", self.html)
        self.assertNotIn("free PDF sample", self.html.lower())

    def test_prices_are_dynamic_and_currency_gated(self):
        self.assertIn('product.currency == "USD"', self.html)
        self.assertIn("product.price|floatformat:2", self.html)
        self.assertNotIn("US $7.50", self.html)
        self.assertNotIn("US $4.00", self.html)
        self.assertNotIn("US $6.80", self.html)

    def test_checkout_requires_documentary_rights_and_release_flags(self):
        for condition in (
            "product.active",
            "product.metadata.asset_verified",
            "product.metadata.license_verified",
            "product.metadata.quality_approved",
            "product.metadata.factory_publication_permission",
            "product.metadata.checkout_enabled",
            'product.metadata.rights_review_status == "independently_cleared"',
        ):
            self.assertIn(condition, self.html)
        self.assertIn("New purchases are on hold until the file, third-party licenses", self.html)
        self.assertIn('product.metadata.rights_review_status != "independently_cleared"', self.html)
        self.assertIn("Do not pay until verification is complete", self.html)

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

    def _render_with_django(self, product_id, currency="USD", title="Example", *,
                            rights_ready=True, active=True, metadata_overrides=None):
        try:
            from django.conf import settings
            from django.template import Context, Engine
        except ImportError:
            self.skipTest("Django is unavailable in this local environment")
        if not settings.configured:
            self.skipTest("Django settings are not configured")
        template = Engine(
            dirs=[str(TEMPLATE.parent.parent.parent)],
            autoescape=True,
        ).get_template("brands/mojplaywin/product.html")
        metadata = {
            "asset_verified": True,
            "license_verified": True,
            "quality_approved": True,
            "factory_publication_permission": True,
            "checkout_enabled": True,
            "rights_review_status": "independently_cleared" if rights_ready else "independent_evidence_pending",
        }
        if metadata_overrides:
            metadata.update(metadata_overrides)
        product = SimpleNamespace(
            pk=product_id, title=title, price=Decimal("7.50"),
            currency=currency, active=active, metadata=metadata,
            description="Untrusted source text",
        )
        return template.render(Context({"product": product}))

    def test_django_render_has_one_distinct_offer_per_current_sku(self):
        for product_id, detail in (
            (72, "415 pages"), (225, "40 pages"), (879, "five SVG illustrations"),
        ):
            with self.subTest(sku=product_id):
                html = self._render_with_django(product_id)
                self.assertIn(detail, html)
                self.assertIn(f'/commerce/book/{product_id}/', html)
                self.assertIn("US $7.50", html)

    def test_django_preview_stays_in_its_own_product_branch(self):
        chess = self._render_with_django(72)
        story = self._render_with_django(225)
        site = self._render_with_django(879)
        self.assertIn('chess-improvement.webp', chess)
        self.assertNotIn('taniya-baker-worms.webp', chess)
        self.assertNotIn('/site-preview', chess)
        self.assertIn('taniya-baker-worms.webp', story)
        self.assertNotIn('chess-improvement.webp', story)
        self.assertNotIn('/site-preview', story)
        self.assertIn('/site-preview', site)
        self.assertNotIn('chess-improvement.webp', site)
        self.assertNotIn('taniya-baker-worms.webp', site)

    def test_django_render_never_advertises_trial_or_wrong_currency(self):
        self.assertNotIn('/commerce/book/779/', self._render_with_django(779))
        self.assertNotIn('/commerce/book/72/', self._render_with_django(72, "EUR"))

    def test_django_render_blocks_sale_when_legal_evidence_is_pending(self):
        for sku in (72, 225, 879):
            with self.subTest(sku=sku):
                html = self._render_with_django(sku, rights_ready=False)
                self.assertNotIn(f'/commerce/book/{sku}/', html)
                self.assertIn('New purchases are on hold', html)
                self.assertIn('Rights and source provenance have not been independently cleared', html)

    def test_django_render_blocks_sale_if_any_release_flag_is_false(self):
        for flag in (
            "asset_verified", "license_verified", "quality_approved",
            "factory_publication_permission", "checkout_enabled",
        ):
            with self.subTest(flag=flag):
                html = self._render_with_django(879, metadata_overrides={flag: False})
                self.assertNotIn('/commerce/book/879/', html)
        self.assertNotIn('/commerce/book/72/', self._render_with_django(72, active=False))

    def test_django_render_escapes_untrusted_product_title(self):
        html = self._render_with_django(72, title='<img src=x onerror=alert(1)>')
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', html)
        self.assertNotIn('<img src=x onerror=alert(1)>', html)


if __name__ == "__main__":
    unittest.main()

