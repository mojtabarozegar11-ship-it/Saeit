"""Regression checks: editorial draft URLs must not leak into public sitemaps."""
from django.test import SimpleTestCase, override_settings

from core.mojplaywin_specialties import SPECIALTIES


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinSitemapSafetyTests(SimpleTestCase):
    def test_editorial_draft_urls_are_absent_from_sitemap(self):
        response = self.client.get("/sitemap.xml", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        for key in SPECIALTIES:
            with self.subTest(key=key):
                self.assertNotIn(("/" + key + "/").encode(), response.content)

    def test_unrelated_site_sitemap_has_no_specialty_drafts(self):
        response = self.client.get("/sitemap.xml", HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code, 200)
        for key in SPECIALTIES:
            with self.subTest(key=key):
                self.assertNotIn(("/" + key + "/").encode(), response.content)
