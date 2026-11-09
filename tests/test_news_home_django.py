"""Public news route uses the approval gate and hides unsigned legacy rows."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from core.news_views import news_home


class NewsHomeTests(SimpleTestCase):
    def test_only_signed_published_company_or_sourced_world_stories(self):
        signed = SimpleNamespace(body="تحلیل علمی مستند\n#مجتبی_روزگار")
        unsigned = SimpleNamespace(body="گزارش قدیمی بدون امضا")
        with (
            patch("core.news_views.NewsletterStory.objects.filter") as query,
            patch("core.news_views.visible_news_stories", return_value=[signed, unsigned]) as gate,
            patch("core.news_views.render") as render,
        ):
            news_home(RequestFactory().get("/news/"))
        kwargs = query.call_args.kwargs
        self.assertEqual(kwargs["status"], "published")
        self.assertEqual(kwargs["story_type__in"], ("company", "world"))
        self.assertIn("published_at__lte", kwargs)
        self.assertEqual(gate.call_args.kwargs["limit"], 60)
        self.assertEqual(render.call_args.args[1], "core/news.html")
        self.assertEqual(render.call_args.args[2]["stories"], [signed])
