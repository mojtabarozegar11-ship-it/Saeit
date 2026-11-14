"""C14: enforce the additive six-link sales conversion block on the legacy static services source."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import unittest

from core.service_sales_controls import SERVICE_CARDS

ROOT = Path(__file__).resolve().parents[1]
STATIC_SERVICES = ROOT / "content" / "zomorod-nova-pages" / "services.html"
MARKER = "zm-six-confirmed-service-scopes-c14"

class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.sections = []
        self.forms = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "section":
            self.sections.append(attrs.get("id", ""))
        if tag == "form":
            self.forms += 1

class StaticServiceLinkTests(unittest.TestCase):
    def setUp(self):
        self.page = STATIC_SERVICES.read_text("utf-8")
        self.parsed = LinkCollector()
        self.parsed.feed(self.page)

    def test_c14_sales_block_is_one_exact_additive_section(self):
        self.assertEqual(self.parsed.sections.count(MARKER), 1)
        self.assertEqual(self.page.count('id="zm-service-scopes-c14-title"'), 1)
        self.assertIn('id="zm-services-action-hub-20261106"', self.page)
        self.assertIn('id="zm-service-deliverables-20261106"', self.page)

    def test_six_exact_public_live_destinations_have_non_empty_titles(self):
        self.assertEqual(len(SERVICE_CARDS), 6)
        for code, offer in SERVICE_CARDS.items():
            url = f"/services/scope/{code}/"
            self.assertEqual(self.parsed.links.count(url), 1)
            self.assertIn(offer["title_fa"], self.page)

    def test_proposals_are_above_legacy_entry_hub(self):
        self.assertLess(
            self.page.index('id="'+MARKER+'"'),
            self.page.index('id="zm-services-action-hub-20261106"'),
        )

    def test_source_has_no_shadow_public_form(self):
        block = self.page.split('<section id="'+MARKER+'"', 1)[1].split('</section>', 1)[0]
        self.assertNotIn('<form', block.lower())
        self.assertIn("/ask-master/index.php", self.page)
        self.assertIn("این صفحه هیچ داده شخصی دریافت یا ذخیره نمی‌شود", self.page)

    def test_existing_presentation_not_replaced(self):
        self.assertIn("zm-unified-v7", self.page)
        self.assertIn("/assets/zm-nova-detail-v1.css", self.page)
        self.assertIn("zm-farm-margin-calculator-20261106", self.page)
        self.assertIn('href="/research/"', self.page)

if __name__ == "__main__":
    unittest.main()
