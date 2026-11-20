from django.test import SimpleTestCase


class MojPropStarter30PublicRouteTests(SimpleTestCase):
    def test_nonpayable_starter30_information_page_is_served(self):
        response = self.client.get("/moj-prop/starter-30-trx/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MOJPROP-STARTER30")
        self.assertContains(response, "Payment not enabled")
        self.assertContains(response, "No funded account is included")
        self.assertContains(response, "Do not send TRX")

    def test_starter30_route_does_not_expose_a_payment_form(self):
        response = self.client.get("/moj-prop/starter-30-trx/")
        self.assertNotContains(response, "payment-form")
        self.assertNotContains(response, "checkout")
        self.assertNotContains(response, "wallet address")
