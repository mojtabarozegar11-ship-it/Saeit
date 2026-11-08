"""Offline end-to-end shape checks for the read-only public delivery gate."""

import unittest
from datetime import date, timedelta

from deploy.newsroom_public_delivery_audit import (
    _fetch_fixed_path,
    inspect_delivery,
)


def _story(*, signature=True, days=7, provinces=31, outside_signature=False):
    date0 = date(2026, 11, 8)
    parts = ['<section class="newsletter-original-report"><span>ORIGINAL REPORT</span>']
    for i in range(provinces):
        parts.append(f"<p>استان {i} — مرکز {i} | دامنه دمای ۷ روز: 1 تا 4 درجه</p>")
        for d in range(days):
            day = (date0 + timedelta(days=d)).isoformat()
            parts.append(f"<p>• {day}: دما 1 تا 4°C؛ بارش 0 میلی‌متر</p>")
    if signature:
        parts.append("<p>#مجتبی_روزگار</p>")
    parts.append("</section>")
    if outside_signature:
        parts.append("<footer>#مجتبی_روزگار</footer>")
    return "<html><head><script>• 2026-11-08: false claim</script></head><body>" + "".join(parts) + "</body></html>"


class PublicDeliveryAuditTests(unittest.TestCase):
    def test_all_seven_days_and_exact_story_signature_pass(self):
        result = inspect_delivery(
            "<main>پیش‌بینی هفت روزه با داده زنده</main>",
            "<main>اخبار و پژوهش جدید با منبع رسمی</main>",
            _story(), report_date="2026-11-08",
        )
        self.assertTrue(result["public_delivery_gate_passed"])
        self.assertEqual(result["story_daily_rows"], 217)
        self.assertEqual(result["story_province_headers"], 31)
        self.assertEqual(len(result["story_daily_rows_by_date"]), 7)

    def test_live_static_pages_and_one_day_bulletin_fail_closed(self):
        result = inspect_delivery(
            "<main>این صفحه فعلاً پیش‌بینی زنده منتشر نمی‌کند.</main>",
            "<main>در این صفحه خبر فوری یا دستاورد تأییدنشده درج نشده است.</main>",
            _story(days=1, signature=False), report_date="2026-11-08",
        )
        self.assertFalse(result["public_delivery_gate_passed"])
        self.assertEqual(result["story_daily_rows"], 31)
        self.assertTrue(result["weather_page_disclaims_live_forecast"])
        self.assertTrue(result["news_page_is_company_information"])

    def test_footer_signature_outside_story_does_not_count(self):
        result = inspect_delivery("healthy", "healthy", _story(signature=False, outside_signature=True), report_date="2026-11-08")
        self.assertTrue(result["story_seven_days_31_provinces"])
        self.assertFalse(result["story_exact_final_signature"])
        self.assertFalse(result["public_delivery_gate_passed"])

    def test_void_html_tags_cannot_erase_end_signature(self):
        story = _story().replace("<span>ORIGINAL REPORT</span>", "<span>ORIGINAL REPORT</span><br/><img src=\"cover.png\"/>")
        result = inspect_delivery("healthy", "healthy", story, report_date="2026-11-08")
        self.assertTrue(result["story_seven_days_31_provinces"])
        self.assertTrue(result["story_exact_final_signature"])

    def test_fewer_provinces_or_missing_story_section_fail(self):
        result = inspect_delivery("healthy", "healthy", _story(provinces=30), report_date="2026-11-08")
        self.assertFalse(result["story_seven_days_31_provinces"])
        missing = inspect_delivery("healthy", "healthy", "<main>• 2026-11-08: fake</main>", report_date="2026-11-08")
        self.assertFalse(missing["story_original_report_found"])
        self.assertFalse(missing["story_exact_final_signature"])

    def test_unapproved_paths_rejected_before_network(self):
        for path in ("http://example.com", "/admin/", "/news/../admin/", "/newsletter/random/"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                _fetch_fixed_path(path)


if __name__ == "__main__":
    unittest.main()
