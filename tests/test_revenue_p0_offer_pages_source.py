"""Source-only structural contract for the two real service inquiry CTAs.

This deliberately does NOT claim live deployment, settlement or delivery.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FA = ROOT / "core/templates/core/services.html"
EN = ROOT / "core/templates/mojplaywin/section.html"
LEGACY = ROOT / "core/templates/brands/mojplaywin/page.html"
PROTOCOL = ROOT / "docs/revenue-p0/intake-and-kpi-operating-protocol.md"


class RevenueP0SourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fa = FA.read_text(encoding="utf-8")
        cls.en = EN.read_text(encoding="utf-8")
        cls.legacy = LEGACY.read_text(encoding="utf-8")

    def test_fa_has_one_service_inquiry(self):
        self.assertEqual(self.fa.count('id="farm-break-even-inquiry"'), 1)
        self.assertIn('href="/contact/"', self.fa)
        self.assertIn("قیمت، محدوده کار، زمان تحویل", self.fa)
        self.assertIn("ثبت استعلام", self.fa)

    def test_en_has_one_service_inquiry(self):
        self.assertEqual(self.en.count('id="website-checkout-inquiry"'), 1)
        self.assertIn("{% if request.path == '/services/' %}", self.en)
        self.assertIn("Request a manual quote by email", self.en)
        self.assertIn("No automatic checkout", self.en)

    def test_legacy_has_one_service_inquiry(self):
        self.assertEqual(self.legacy.count('id="website-checkout-inquiry"'), 1)
        self.assertIn("{% if page_key == 'services' %}", self.legacy)
        self.assertIn("Request manual service quote", self.legacy)

    def test_valid_support_destination(self):
        for source in (self.en, self.legacy):
            self.assertIn("mailto:mojplaywin@gmail.com?subject=", source)
            self.assertIn("USD 29", source)
            self.assertIn("USD 79", source)

    def test_existing_template_structure_preserved(self):
        self.assertIn("<section class=\"services-grid\">", self.fa)
        self.assertIn("<section class=\"services-map\"", self.fa)
        self.assertIn('class="mw-page-hero"', self.en)
        self.assertIn('{% if active_venture %}', self.en)
        self.assertIn('id="guide-services"', self.legacy)

    def test_source_has_no_new_payment_buttons(self):
        for section in (
            self.fa.split('id="farm-break-even-inquiry"', 1)[1].split("</section>", 1)[0],
            self.en.split('id="website-checkout-inquiry"', 1)[1].split("</section>", 1)[0],
            self.legacy.split('id="website-checkout-inquiry"', 1)[1].split("</section>", 1)[0],
        ):
            self.assertNotIn("Buy now", section)
            self.assertNotIn("Pay now", section)
            self.assertNotIn("TRX address", section)

    def test_protocol_separates_evidence_gates(self):
        source = PROTOCOL.read_text(encoding="utf-8")
        for gate in ("SOURCE:", "LIVE:", "COMMERCE:", "DELIVERY:",
                     "UNKNOWN", "mojtaba.bot.ai"):
            self.assertIn(gate, source)


if __name__ == "__main__":
    unittest.main()
