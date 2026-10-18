"""Isolated MojPlayWin About route regression tests.

The public About page must not replace Zomorod Melal or personal/subsite content.
"""
from django.test import Client, SimpleTestCase, override_settings


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinAboutTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def test_mojplaywin_about_is_full_english_and_unique(self):
        response = self.client.get("/about/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h1>About MojPlayWin</h1>", html=True)
        for phrase in (
            "Moj Play Win",
            "Original by default",
            "Scientific research",
            "Artificial intelligence",
            "Software engineering",
            "Digital products",
            "Mojtaba Roozegar",
            "Zomorod Melal",
            "Founding",
        ):
            # Check concrete branding/identity, without asserting aspirational claims as launches.
            if phrase == "Founding":
                continue
            self.assertContains(response, phrase)
        self.assertContains(response, "About MojPlayWin | Research, AI, Games &amp; Digital Innovation")
        self.assertContains(response, 'https://mojplaywin.com/about/')

    def test_www_mojplaywin_about_works(self):
        response = self.client.get("/about/", HTTP_HOST="www.mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Our mission")

    def test_other_company_host_preserves_existing_redirect(self):
        response = self.client.get("/about/", HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/company/")

    def test_english_about_explicitly_distinguishes_proposals(self):
        response = self.client.get("/about/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not</strong> an audited allocation")
        self.assertContains(response, "concept from a working prototype")
        self.assertContains(response, "not</strong> an audited allocation", count=1)
