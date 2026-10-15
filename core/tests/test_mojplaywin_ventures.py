from django.test import TestCase, override_settings
from django.urls import reverse

@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.com"])
class MojPlayWinVentureTests(TestCase):
    def test_all_venture_pages_render_complete_content(self):
        slugs = ["agriculture", "cafe-restaurant", "fuel-station", "jewelry-gold", "carpets", "currency-crypto", "ecommerce", "hospitality"]
        for slug in slugs:
            with self.subTest(slug=slug):
                response = self.client.get(reverse("mojplaywin_venture", kwargs={"slug": slug}), HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "mw-page-hero")
                self.assertContains(response, "mw-card")
                self.assertContains(response, "Explore connected fields")

    def test_venture_pages_are_scoped_to_mojplaywin_host(self):
        response = self.client.get(reverse("mojplaywin_venture", kwargs={"slug": "ecommerce"}), HTTP_HOST="zomorodmelal.com")
        self.assertEqual(response.status_code, 404)

    def test_home_explains_80_20_focus_and_links_ventures(self):
        response = self.client.get("/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OUR PORTFOLIO")
        self.assertContains(response, "CONNECTED VENTURES")
        self.assertContains(response, "/ventures/currency-crypto/")
        self.assertContains(response, "/ventures/fuel-station/")
