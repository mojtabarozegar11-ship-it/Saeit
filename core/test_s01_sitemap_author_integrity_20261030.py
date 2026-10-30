"""S-01 no-DB regressions: truthful sitemap outage and safe static author read."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from core import seo_views


class SitemapOutageTests(SimpleTestCase):
    def test_missing_catalog_table_returns_retryable_uncached_503(self):
        request = RequestFactory().get("/sitemap.xml")
        with patch.object(seo_views, "missing_public_tables", return_value=True) as guard:
            response = seo_views.sitemap_xml(request)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-ZM-Data-Status"], "temporarily-unavailable")
        self.assertNotIn("<urlset", response.content.decode("utf-8"))
        self.assertEqual(len(guard.call_args.args), 6)


class AuthorStaticIntegrityTests(SimpleTestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile_dir = self.root / "public" / "authors" / "mojtaba-rozegar"
        self.profile_dir.mkdir(parents=True)
        self.page = self.profile_dir / "index.html"
        self.request = RequestFactory().get("/authors/mojtaba-rozegar/")

    def response(self):
        with override_settings(BASE_DIR=self.root):
            return seo_views.persian_author_profile(self.request)

    def test_valid_html_is_byte_preserved(self):
        data = "<html lang='fa'>\u0645\u062c\u062a\u0628\u06cc</html>".encode("utf-8")
        self.page.write_bytes(data)
        response = self.response()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, data)

    def test_symlinked_intermediate_directory_is_not_followed(self):
        self.page.write_text("safe", encoding="utf-8")
        original = self.root / "public"
        moved = self.root / "real-public"
        original.rename(moved)
        original.symlink_to(moved, target_is_directory=True)
        self.assertEqual(self.response().status_code, 404)

    def test_hardlinked_public_profile_is_not_served(self):
        self.page.write_text("safe", encoding="utf-8")
        os.link(self.page, self.root / "alias.html")
        self.assertEqual(self.response().status_code, 503)

    def test_oversized_profile_is_not_served(self):
        self.page.write_bytes(b"x" * 1_000_001)
        self.assertEqual(self.response().status_code, 503)


class SearchOutageTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/search/?q=agriculture")

    def test_missing_search_schema_returns_retryable_nonempty_503(self):
        with patch.object(seo_views, "missing_public_tables", return_value=True), \\
             patch.object(seo_views, "_site_search_with_schema") as query:
            response = seo_views.site_search(self.request)
        query.assert_not_called()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "300")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn("temporarily-unavailable", response["X-ZM-Data-Status"])
        self.assertIn("جست‌وجو", response.content.decode("utf-8"))

    def test_database_failure_after_schema_check_fails_closed(self):
        from django.db import DatabaseError
        with patch.object(seo_views, "missing_public_tables", return_value=False), \\
             patch.object(seo_views, "_site_search_with_schema", side_effect=DatabaseError):
            response = seo_views.site_search(self.request)
        self.assertEqual(response.status_code, 503)

    def test_healthy_search_uses_original_renderer(self):
        from django.http import HttpResponse
        expected = HttpResponse("search is ready")
        with patch.object(seo_views, "missing_public_tables", return_value=False), \\
             patch.object(seo_views, "_site_search_with_schema", return_value=expected):
            response = seo_views.site_search(self.request)
        self.assertIs(response, expected)
