"""Model-level regression tests; run under the project's configured Django suite."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.utils import timezone

from core.newsletter_models import NewsletterPublication, NewsletterStory


class NewsletterPublishGateTests(SimpleTestCase):
    def make_story(self, *, status="published", body="متن خبر", published_at=None):
        return NewsletterStory(
            status=status,
            story_type="report",
            title="گزارش تخصصی کشاورزی",
            slug="agriculture-news-signature-check",
            summary="گزارش علمی درباره عملکرد محصول",
            body=body,
            fingerprint="signature-gate-check",
            published_at=published_at or timezone.now() - timedelta(minutes=1),
        )

    def test_published_news_requires_exact_final_signature(self):
        story = self.make_story(body="متن خبر فاقد امضا")
        with self.assertRaises(ValidationError):
            story.clean()
        story.body = "متن خبر\n\n#مجتبی_روزگار"
        story.clean()

    def test_draft_can_be_edited_before_signature_is_added(self):
        self.make_story(status="draft", body="پیش‌نویس قابل بازبینی").clean()

    def test_distribution_refuses_unsigned_or_future_news(self):
        unsigned = self.make_story(body="متن بدون امضا")
        with self.assertRaises(ValidationError):
            NewsletterPublication(story=unsigned, status="published", channel="site").save()
        future = self.make_story(
            body="گزارش\n\n#مجتبی_روزگار", published_at=timezone.now() + timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            NewsletterPublication(story=future, status="published", channel="site").save()
