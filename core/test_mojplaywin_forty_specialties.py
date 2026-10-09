from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from django.utils.html import escape

from core.mojplaywin_specialties import SPECIALTIES
from core.mojplaywin_specialty_views import specialty_page


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinFortySpecialtyTests(SimpleTestCase):
    def test_exact_25_product_and_15_service_pages(self):
        self.assertEqual(sum(x["kind"] == "products" for x in SPECIALTIES.values()), 25)
        self.assertEqual(sum(x["kind"] == "services" for x in SPECIALTIES.values()), 15)
        self.assertEqual(len(SPECIALTIES), 40)

    def test_every_specialty_is_distinct_and_draft(self):
        self.assertEqual(len({v["title"] for v in SPECIALTIES.values()}), 40)
        for key, item in SPECIALTIES.items():
            with self.subTest(key=key):
                self.assertTrue(all(item[field].strip() for field in ("intro", "focus", "checks", "workflow")))
                self.assertEqual(item["status"], "editorial_draft")
                self.assertEqual(resolve("/" + key + "/").func, specialty_page)

    def test_all_40_pages_render_with_noindex_and_navigation(self):
        for key, item in SPECIALTIES.items():
            with self.subTest(key=key):
                response = self.client.get("/" + key + "/", HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["X-Robots-Tag"], "noindex, follow, noarchive")
                self.assertEqual(response["Cache-Control"], "private, no-store")
                self.assertContains(response, escape(item["title"]))
                self.assertContains(response, item["focus"])
                self.assertContains(response, item["checks"])
                self.assertContains(response, 'rel="canonical"')
                self.assertContains(response, "Not currently available for checkout")
                self.assertContains(response, "/" + item["kind"] + "/")

    def test_hubs_link_every_dedicated_page(self):
        for kind in ("products", "services"):
            with self.subTest(kind=kind):
                response = self.client.get("/" + kind + "/", HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                for key, item in SPECIALTIES.items():
                    if item["kind"] == kind:
                        self.assertContains(response, "/" + key + "/")
                        self.assertContains(response, escape(item["title"]))

    def test_no_checkout_or_price_claim_on_drafts(self):
        for key in SPECIALTIES:
            with self.subTest(key=key):
                response = self.client.get("/" + key + "/", HTTP_HOST="mojplaywin.com")
                self.assertNotContains(response, 'name="quantity"')
                self.assertNotContains(response, 'type="submit"')
                self.assertNotContains(response, 'Add to cart')
                self.assertContains(response, "Editorial draft")

    def test_release_journey_is_rendered_on_every_page(self):
        for key in SPECIALTIES:
            with self.subTest(key=key):
                response = self.client.get("/" + key + "/", HTTP_HOST="mojplaywin.com")
                self.assertContains(response, "How this specialty moves from concept to release")
                self.assertContains(response, "Discover")
                self.assertContains(response, "Build")
                self.assertContains(response, "Verify")
                self.assertContains(response, "Approve")
                self.assertContains(response, 'class="mpw-specialty-steps"')

    def test_other_brand_is_not_exposed(self):
        response = self.client.get("/products/software-products/", HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code, 404)

    def test_unknown_specialty_is_404(self):
        response = self.client.get("/services/not-a-real-service/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 404)
