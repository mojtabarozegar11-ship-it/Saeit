"""C17: service-specific alternative contact without a shadow web form."""
import re
import unittest

from scripts.build_company_service_static_c13 import (
    CONTACT, CODES, ROOT, html_page, literal,
)


class C17DirectEmailFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.offers = literal("_SERVICES", ROOT / "core" / "service_sales_controls.py")
        cls.guides = literal("SCOPE_GUIDES", ROOT / "core" / "service_scope_pages.py")

    def test_six_scopes_have_both_canonical_php_and_optional_email(self):
        for code in CODES:
            with self.subTest(code=code):
                page = html_page(code, self.offers[code], self.guides[code])
                self.assertIn('class="scope-primary-cta" href="'+CONTACT+'"', page)
                self.assertIn("mailto:zomorodmelal@gmail.com?subject=", page)
                self.assertIn("%5B" + code + "%5D", page)
                self.assertIn('class="scope-email-fallback"', page)
                self.assertIn("هیچ پیامی از این صفحه به صورت خودکار ارسال نمی‌شود", page)

    def test_email_links_are_subject_only_never_personal_information(self):
        for code in CODES:
            page = html_page(code, self.offers[code], self.guides[code])
            self.assertEqual(page.count("mailto:zomorodmelal@gmail.com?subject="), 1)
            self.assertNotIn("mailto:zomorodmelal@gmail.com?body=", page)
            self.assertNotIn("&body=", page)
            self.assertNotIn("<form", page.casefold())
            self.assertNotIn("fetch(", page)
            self.assertNotIn("XMLHttpRequest", page)
            self.assertNotIn("sendBeacon", page)

    def test_all_six_have_unique_no_network_subjects(self):
        subjects = set()
        for code in CODES:
            page = html_page(code, self.offers[code], self.guides[code])
            m = re.search(r'href="mailto:zomorodmelal@gmail.com\?subject=([^"]+)"', page)
            self.assertIsNotNone(m)
            self.assertNotIn(m.group(1), subjects)
            subjects.add(m.group(1))
        self.assertEqual(len(subjects), 6)


if __name__ == "__main__":
    unittest.main()
