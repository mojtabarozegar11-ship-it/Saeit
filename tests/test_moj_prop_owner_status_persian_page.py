"""Truthful Persian informational page: one owner-active plan, nine on hold."""
import unittest
from html.parser import HTMLParser
from prop_firm.site import render_site


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = 0
        self.inputs = 0
        self.forms = 0
    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.rows += 1
        if tag == "input":
            self.inputs += 1
        if tag == "form":
            self.forms += 1


class TenPlanPersianPageTests(unittest.TestCase):
    def setUp(self):
        self.document = render_site()

    def test_all_ten_skus_are_visible_and_not_stored_as_static_guess(self):
        for n in range(1, 11):
            with self.subTest(n=n):
                self.assertIn(f"MOJ-PROP-{n:02d}", self.document)
        p=Tags()
        p.feed(self.document)
        self.assertEqual(p.rows, 11)  # header and exactly 10 plan rows

    def test_owner_status_and_nine_held_plan_rows(self):
        self.assertEqual(self.document.count("فعال و تأمین سرمایه‌شده طبق اعلام مالک"), 1)
        self.assertEqual(self.document.count("در حال تأمین سرمایه؛ موقتاً غیرفعال"), 9)
        self.assertIn("نه مدرک مستقل موجودی بانکی", self.document)

    def test_owner_entry_fee_and_plan10_price_remain_distinct(self):
        self.assertIn("30 TRX", self.document)
        self.assertIn("2000 TRX", self.document)
        self.assertIn("تعرفه‌های پلن‌های ۲ تا ۱۰ پیشنهادی‌اند", self.document)

    def test_source_contains_only_one_persian_page_not_legacy_appended_tail(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "prop_firm/site.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(source.count("def render_site():"), 1)
        self.assertEqual(source.count("return f'''<!doctype html>"), 1)
        self.assertEqual(source.count('if __name__ == "__main__":'), 1)
        self.assertTrue(source.rstrip().endswith("build_site(parser.parse_args().output)"))

    def test_informational_page_never_accepts_orders(self):
        p=Tags()
        p.feed(self.document)
        self.assertEqual(p.forms, 0)
        self.assertEqual(p.inputs, 0)
        self.assertIn('name="robots" content="noindex,nofollow"', self.document)
        self.assertNotIn('private_key', self.document.lower())
        self.assertNotIn('contract wallet', self.document.lower())


if __name__ == "__main__":
    unittest.main()
