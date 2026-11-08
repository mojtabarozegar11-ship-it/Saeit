"""Offline checks for the mandatory no-politics/no-Israel news rule."""

import unittest
from types import SimpleNamespace

from core.editorial_policy import (
    blocked_news_reason, blocked_story_reason, visible_news_stories, visible_story_links,
)


class EditorialPolicyTests(unittest.TestCase):
    def test_israel_multiple_scripts_and_unicode_spellings(self):
        for text in (
            "اسرائیل", "اسراییل", "إسرائيل", "Israel", "Israeli",
            "TEL AVIV", "Jerusalem", "صهیونیست", "ישראל", "تل‌آویو",
            "https://example.org/news/Isra%65l/farming",
            "Gaza agriculture update", "West Bank farm report", "Knesset vote",
            "Netanyahu statement", "Mossad report", "Haifa weather",
            "IDF briefing", "غزه", "کرانه باختری", "نتانیاهو",
            "القدس", "حیفا", "الكنيست", "עזה", "נתניהו",
        ):
            with self.subTest(text=text):
                self.assertEqual(blocked_news_reason(text), "israel_related")

    def test_political_titles_are_blocked(self):
        for text in (
            "انتخابات مجلس", "گزارش وزیر کشاورزی", "اخبار سیاسی",
            "government election", "Agricultural sanctions debated in parliament",
            "Diplomatic statement", "War in region", "رئیس‌جمهور",
            "Lawmakers vote", "foreign policy debate", "White House statement",
            "National security meeting", "خبر استاندار", "فرماندار اعلام کرد",
            "الحكومة", "الرئيس", "الجيش",
        ):
            with self.subTest(text=text):
                self.assertEqual(blocked_news_reason(text), "political_news")

    def test_neutral_agricultural_and_weather_news_pass_lexical_gate(self):
        for text in (
            "آمار برداشت گندم و پیش‌بینی باران در شمال کشور",
            "FAO report: agricultural yields and food prices",
            "USDA crop production and soil moisture data",
            "گزارش هفت‌روزه هواشناسی استان‌های ایران",
        ):
            with self.subTest(text=text):
                self.assertIsNone(blocked_news_reason(text))

    def test_checks_full_body_and_source_not_only_title(self):
        story = SimpleNamespace(
            title="گزارش برداشت محصول", summary="آمار هفتگی", body="بدون مشکل",
            seo_keywords=["کشاورزی"],
            source=SimpleNamespace(title="Agricultural update", publisher="FAO", url="https://fao.org/israel/brief"),
        )
        self.assertEqual(blocked_story_reason(story), "israel_related")
        story.source.url = "https://fao.org/agriculture"
        story.body = "This report discusses elections."
        self.assertEqual(blocked_story_reason(story), "political_news")

    def test_no_match_is_not_editorial_approval(self):
        self.assertIsNone(blocked_news_reason("harvest index"))

    def test_forest_and_seed_selection_are_not_political_keywords(self):
        self.assertIsNone(blocked_news_reason("انتخاب بذر مناسب و حفاظت از جنگل‌های شمال"))

    def test_legacy_items_removed_from_public_collections(self):
        class FakeQuerySet:
            def __init__(self, items):
                self.items = items

            def select_related(self, *_):
                return self

            def __getitem__(self, key):
                return self.items[key]

        def story(title):
            return SimpleNamespace(title=title, body="کشاورزی", summary="", source=None, seo_keywords=[])

        safe = story("Crop report")
        blocked = story("Israel crop report")
        self.assertEqual(visible_news_stories(FakeQuerySet([blocked, safe]), limit=2), [safe])
        links = [SimpleNamespace(newsletter_story=blocked), SimpleNamespace(newsletter_story=safe)]
        self.assertEqual(visible_story_links(links), [links[1]])


if __name__ == "__main__":
    unittest.main()
