"""Main-site only: template and SEO regressions must not touch other hosts or subsites."""
from django.test import RequestFactory, TestCase, override_settings
from django.template.loader import render_to_string


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinIsolatedLayoutTests(TestCase):
    def test_main_site_has_one_header_footer_and_english_metadata(self):
        for path in ("/", "/store/", "/research/", "/knowledge/", "/industry/", "/market/", "/agents/", "/company/"):
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                self.assertEqual(html.count('<header class="mw-site-nav"'), 1)
                self.assertEqual(html.count('<footer class="mw-site-footer"'), 1)
                self.assertNotIn('<header class="site-header"', html)
                self.assertNotIn('<footer class="site-footer"', html)
                self.assertNotIn('aria-label="Zomorodmelal"', html)
                self.assertIn('<html lang="en" dir="ltr">', html)
                self.assertIn('href="https://mojplaywin.com' + path + '"', html)
                # The owner-approved footer is now a *single line* legal notice.
                # Keep the test in sync with that exact published contract, not
                # the superseded separate copyright and founder spans.
                self.assertEqual(html.count('data-mpw-final-founder="true"'), 1)
                self.assertEqual(
                    html.count("☆ All Rights Reserved. ☆ 2022. ☆ Mojtaba roozegar ☆"), 1
                )
                self.assertEqual(html.count('class="mpw-legal-one-line"'), 1)
                self.assertNotIn('data:image/jpeg;base64,', html)

    def test_seo_titles_are_unique_by_section(self):
        paths = ("/", "/store/", "/research/", "/knowledge/", "/industry/")
        titles = []
        for path in paths:
            html = self.client.get(path, HTTP_HOST="mojplaywin.com").content.decode("utf-8")
            self.assertEqual(html.count("<title>"), 1)
            self.assertEqual(html.count('name="description"'), 1)
            titles.append(html.split("<title>", 1)[1].split("</title>", 1)[0])
        self.assertEqual(len(titles), len(set(titles)))

    def test_legacy_main_pages_share_shell_without_losing_body(self):
        request = RequestFactory().get("/games/", HTTP_HOST="mojplaywin.com")
        page = {"title": "Original Games", "body": "Games and learning", "headline": "Our Games", "kicker": "GAMES", "cards": []}
        html = render_to_string("brands/mojplaywin/page.html", {"page": page, "page_key": "games"}, request=request)
        self.assertEqual(html.count('<header class="mw-site-nav"'), 1)
        self.assertEqual(html.count('<footer class="mw-site-footer"'), 1)
        self.assertIn("Our Games", html)
        self.assertNotIn('class="mpw-header"', html)
        self.assertNotIn('class="mpw-footer"', html)

    def test_other_company_host_keeps_its_original_renderer(self):
        response = self.client.get("/", HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertNotIn('data-design="mojplaywin-atelier-v4"', html)
        self.assertNotIn('data-mpw-copyright-founder="true"', html)
