"""Ensure the featured Taniya book drives real guest-TRX checkout discovery."""
from django.test import SimpleTestCase, override_settings


class TaniyaExistingBookCheckoutLink(SimpleTestCase):
    @override_settings(ALLOWED_HOSTS=["mojplaywin.com", "zomorodmelal.ir", "testserver"])
    def test_public_taniya_book_uses_owned_existing_guest_checkout(self):
        response = self.client.get("/taniya/", HTTP_HOST="mojplaywin.com", secure=True)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("<h3>Taniya and the Little Baker Worms</h3>", body)
        self.assertIn('<a class="book-buy" href="/commerce/book/225/">', body)
        self.assertIn("Buy this illustrated storybook with TRX", body)
        self.assertNotIn("mailto:hello@mojplaywin.com?subject=Order%20Taniya", body)
        self.assertNotIn("/mojprop-starter30-checkout/", body)

    @override_settings(ALLOWED_HOSTS=["mojplaywin.com", "zomorodmelal.ir", "testserver"])
    def test_other_company_host_keeps_existing_taniya_redirect(self):
        response = self.client.get("/taniya/", HTTP_HOST="zomorodmelal.ir", secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://mojplaywin.com/taniya/")
