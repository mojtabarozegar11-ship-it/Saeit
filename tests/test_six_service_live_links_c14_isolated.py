"""Standalone six-service navigation regression for an isolated main-based patch."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "content/zomorod-nova-pages/services.html"
OFFER_LINKS = {
    "AGR-01": "تحلیل اقتصاد و سودآوری مزرعه",
    "RS-01": "ممیزی شاخص‌های پژوهش کشاورزی",
    "RS-02": "ممیزی سناریوی آبیاری",
    "RS-03": "طراحی آزمایش و بررسی اقتصادی تحقیق",
    "WEB-01": "طراحی مسیر درخواست و فروش کسب‌وکار",
    "SEO-01": "ممیزی فنی و محتوایی سئو",
}

class Parsed(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = []
        self.forms = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "a":
            self.links.append(a.get("href"))
        if tag == "form":
            self.forms += 1

class SixServiceSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = SOURCE.read_text("utf-8")
        cls.parsed = Parsed()
        cls.parsed.feed(cls.html)

    def test_six_independent_real_urls_exactly_once(self):
        for code, title in OFFER_LINKS.items():
            self.assertEqual(self.parsed.links.count(f"/services/scope/{code}/"), 1)
            self.assertIn(title, self.html)

    def test_new_section_is_one_unique_target_near_top(self):
        marker = "zm-six-confirmed-service-scopes-c14"
        self.assertEqual(self.parsed.ids.count(marker), 1)
        self.assertEqual(self.parsed.ids.count("zm-service-scopes-c14-title"), 1)
        self.assertLess(self.html.index(marker), self.html.index("zm-services-action-hub-20261106"))

    def test_static_page_preserves_existing_theme_and_sales_form(self):
        for text in ("zm-unified-v7", "zm-services-action-hub-20261106",
                     "zm-service-deliverables-20261106", "/assets/zm-nova-detail-v1.css",
                     "/ask-master/index.php"):
            self.assertIn(text, self.html)

    def test_no_shadow_form_or_external_contact_gateway_in_inserted_section(self):
        block = self.html.split('<section id="zm-six-confirmed-service-scopes-c14"', 1)[1].split("</section>", 1)[0]
        self.assertNotIn("<form", block.lower())
        self.assertNotIn("mailto:", block.lower())
        self.assertNotIn("checkout", block.lower())
        self.assertNotIn("https://", block.lower())

if __name__ == "__main__":
    unittest.main()
