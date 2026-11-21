from django.test import SimpleTestCase


class MojPropStarter30PublicRouteTests(SimpleTestCase):
    def test_current_simulated_starter30_information_page_is_served(self):
        response = self.client.get("/moj-prop/starter-30-trx/")
        self.assertEqual(response.status_code, 200)
        for marker in ("MOJPROP-STARTER30", "30 TRX",
                       "No real funded account or customer capital is involved",
                       "server-issued 30 TRX invoice", "$1,000", "60 days", "50%",
                       "does not guarantee that the trader will generate profit or pass"):
            self.assertContains(response, marker)

    def test_starter30_route_does_not_expose_a_payment_form(self):
        response = self.client.get("/moj-prop/starter-30-trx/")
        self.assertNotContains(response, "payment-form")
        self.assertContains(response, '<form action="/mojprop-starter30-status/" method="get"')
        self.assertNotContains(response, 'method="post"')
        self.assertNotContains(response, 'name="payer_address"')
        self.assertNotContains(response, 'name="txid"')
        self.assertContains(response, 'href="/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=starter-30-trx&amp;utm_source=moj_prop&amp;utm_medium=onsite&amp;utm_campaign=starter30_lead&amp;utm_content=free_terms"')
        self.assertNotContains(response, 'href="/mojprop-starter30-checkout/"')
