"""Offline safeguards for the static Shiraz café inquiry landing page."""

import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "public" / "ghanadi"


class PageTags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class GhanadiB2BSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cafe = (ROOT / "cafe-shiraz" / "index.html").read_text(encoding="utf-8")
        cls.main = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.tags = PageTags()
        cls.tags.feed(cls.cafe)

    def test_shiraz_page_has_clear_indexing_and_local_intent(self):
        self.assertIn('rel="canonical" href="https://zomorodmelal.ir/ghanadi/cafe-shiraz/"', self.cafe)
        self.assertIn('name="robots" content="index,follow,max-image-preview:large"', self.cafe)
        self.assertIn("<h1>کوکی و شیرینی برای منوی کافه‌های شیراز</h1>", self.cafe)
        self.assertIn('href="#inquiry"', self.cafe)
        self.assertIn('href="#inquiry">ارسال استعلام کتبی ویژه کافه</a>', self.cafe)

    def test_inquiry_is_a_consent_based_first_party_form(self):
        forms = [attrs for tag, attrs in self.tags.tags if tag == "form"]
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0]["id"], "cafeInquiry")
        self.assertEqual(forms[0]["action"], "/ask-master/index.php")
        self.assertEqual(forms[0]["method"], "post")
        inputs = [attrs for tag, attrs in self.tags.tags if tag in {"input", "select", "textarea"}]
        named = {attrs.get("name"): attrs for attrs in inputs}
        self.assertTrue({"name", "email", "cafe", "district", "product", "quantity",
                         "frequency", "date", "details", "consent"}.issubset(named))
        for required in ("name", "email", "cafe", "district", "product", "quantity", "consent"):
            self.assertIn("required", named[required], required)
        self.assertEqual(named["quantity"]["min"], "1")

    def test_official_php_intake_and_csrf_are_reused(self):
        self.assertIn("fetch('/ask-master/index.php?service=1'", self.cafe)
        self.assertIn('querySelector(\'input[name="csrf"]\')', self.cafe)
        self.assertIn("kind:'service_question'", self.cafe)
        self.assertIn("submission.submit()", self.cafe)
        self.assertNotIn("localStorage", self.cafe)
        self.assertIn("event.preventDefault()", self.cafe)
        self.assertIn('id="cafeInquirySubmit" disabled', self.cafe)
        self.assertIn("document.getElementById('cafeInquirySubmit').disabled=false", self.cafe)
        self.assertIn("<noscript>", self.cafe)

    def test_no_unverified_storefront_claims(self):
        data = re.search(
            r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>',
            self.cafe, flags=re.S
        )
        self.assertIsNotNone(data)
        graph = json.loads(data.group(1))["@graph"]
        service = next(entry for entry in graph if entry["@type"] == "Service")
        self.assertEqual(service["areaServed"]["name"], "شیراز")
        self.assertEqual(service["provider"]["telephone"], "+989382165418")
        self.assertNotIn("address", service["provider"])
        self.assertNotIn("openingHours", service["provider"])
        self.assertIn("قیمت، ظرفیت تولید و تحویل هنوز قطعی نیستند", self.cafe)

    def test_main_page_converts_to_inquiry_not_fake_checkout(self):
        self.assertIn('id="openCart" aria-label="فهرست انتخاب‌ها برای استعلام، بدون خرید قطعی"', self.main)
        self.assertIn('href="/ghanadi/cafe-shiraz/"', self.main)
        self.assertIn('name="description"', self.main)
        self.assertNotIn("tag:'پرفروش'", self.main)
        self.assertIn("استعلام قیمت<small>پس از تعیین نوع و تعداد</small>", self.main)
        self.assertIn("fa(count)+' مورد'", self.main)
        self.assertNotIn("${fa(p.price)} تومان<small>", self.main)


if __name__ == "__main__":
    unittest.main()
