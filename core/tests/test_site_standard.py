from django.test import TestCase


class SiteStandardRegressionTests(TestCase):
    public_routes = (
        "/",
        "/academy/",
        "/agents/",
        "/weather/",
        "/economy/",
        "/studio/",
        "/knowledge/",
        "/company/",
        "/company/executive/",
        "/blog/",
        "/newsletter/",
        "/store/",
        "/auctions/",
        "/company-gallery/",
        "/search/",
    )

    def test_public_pages_use_site_standard_shell(self):
        for path in self.public_routes:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                self.assertIn("site-standard-v2", html)
                self.assertEqual(html.count("<main"), 1)
                self.assertEqual(html.count("</main>"), 1)
                self.assertIn('id="main-content"', html)
                self.assertIn('class="skip-link"', html)

    def test_knowledge_public_view_has_no_internal_engine_dashboard(self):
        response = self.client.get("/knowledge/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        for internal_label in (
            "موتور تحقیق",
            "خط تولید محتوا",
            "CONTENT ENGINE",
            "در حال توسعه",
            "مقصدهای خارجی",
        ):
            self.assertNotIn(internal_label, html)

    def test_site_standard_v2_is_future_guardrail(self):
        response = self.client.get("/knowledge/")
        html = response.content.decode("utf-8")
        self.assertIn("site-standard-v2", html)
        self.assertIn("حوزه‌های دانش", html)
        self.assertIn("کتابخانه تخصصی و دانشنامه‌ای", html)
