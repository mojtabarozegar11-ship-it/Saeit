"""Sitemap must not advertise unapproved or unverified research guide URLs."""

from contextlib import ExitStack
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from core import seo_views


class ResearchGuideSitemapTests(SimpleTestCase):
    def sitemap(self, public_guides):
        models = [
            seo_views.BlogPage, seo_views.NewsletterStory,
            seo_views.KnowledgeArticle, seo_views.KnowledgeBook,
            seo_views.KnowledgeDomain, seo_views.Product,
        ]
        with ExitStack() as stack:
            for model in models:
                manager = stack.enter_context(patch.object(model, "objects"))
                manager.filter.return_value.values_list.return_value = []
                manager.values_list.return_value = []
            stack.enter_context(patch.object(
                seo_views, "verified_guide_paths", return_value=public_guides
            ))
            return seo_views.sitemap_xml(
                RequestFactory().get("/sitemap.xml")
            ).content.decode("utf-8")

    def test_sitemap_has_no_draft_guide_urls(self):
        output = self.sitemap([])
        self.assertIn("<urlset", output)
        self.assertNotIn("/research/guides/guide-one/", output)

    def test_sitemap_includes_only_verified_guide_urls(self):
        output = self.sitemap(["/research/guides/guide-one/"])
        self.assertIn(
            "<loc>https://zomorodmelal.ir/research/guides/guide-one/</loc>",
            output
        )
        self.assertEqual(output.count("/research/guides/guide-one/"), 1)
