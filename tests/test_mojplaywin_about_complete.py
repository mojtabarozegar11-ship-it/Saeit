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
        ):
            # Check concrete branding/identity without claiming a commercial launch.
            self.assertContains(response, phrase)
        self.assertContains(response, "About MojPlayWin | Research, AI, Games & Digital Innovation")
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

    def test_advanced_dossier_contains_real_methods_not_only_promotional_copy(self):
        response = self.client.get("/about/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Research-grade company dossier")
        for phrase in (
            "Research design, epistemology",
            "Quantitative analysis",
            "Large language models",
            "Agent orchestration",
            "Game mechanics",
            "Enterprise web architecture",
            "Digital product lifecycle",
            "Curriculum architecture",
            "Scientific and executive leadership",
        ):
            # Check on-page specialist material is rendered by Django.
            self.assertContains(response, phrase)
        for index in range(1, 29):
            self.assertContains(response, "SPECIALISM %02d" % index)
        for index in range(1, 8):
            self.assertContains(response, 'id="dossier-%d"' % index)
        for domain in ("nist.gov", "w3.org", "owasp.org", "nature.com"):
            self.assertContains(response, domain)
        self.assertContains(response, "do not certify")
        self.assertContains(response, "not evidence")

    def test_complementary_20_percent_contains_ten_industries_and_thirty_disciplines(self):
        response = self.client.get("/about/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The complementary 20%")
        self.assertContains(response, "not an audited portion")
        self.assertContains(response, "distinct brands")
        for phrase in (
            "Agriculture, crop production and agro-industry",
            "Livestock, poultry, aquaculture",
            "Food science, processing and functional nutrition",
            "Precious metals, jewelry, gemstones",
            "Handwoven carpets, textiles",
            "Hospitality, restaurants",
            "International trade, distribution",
            "Industrial production, manufacturing",
            "Fuel stations, mobility",
            "Currency literacy, market research",
            "HACCP",
        ):
            self.assertContains(response, phrase)
        self.assertContains(response, "FAIR")
        self.assertContains(response, "responsible financing")
        for sector in range(1, 11):
            self.assertContains(response, 'id="sector-%02d"' % sector)
        for specialty in range(1, 31):
            self.assertContains(response, "COMPLEMENTARY SPECIALISM %02d" % specialty)
        for source in ("fao.org", "iso.org", "cibjo.org"):
            self.assertContains(response, source)
        self.assertContains(response, "not evidence of a licensed fuel station")

    def test_complementary_industries_do_not_break_other_host_about(self):
        response = self.client.get("/about/", HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/company/")
