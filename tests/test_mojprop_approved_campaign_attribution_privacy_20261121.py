"""Only reviewed UTM tuples reach real unpaid enquiry HTML; no arbitrary echo."""
from django.test import RequestFactory, SimpleTestCase
from core.mojprop_accessible_intake import request_form


class PublicLeadAttributionPrivacyTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _render(self, query):
        return request_form(self.factory.get("/moj-prop-intake/?" + query)).content.decode("utf8")

    def test_signal_campaign_passes_exact_four_safe_hidden_fields(self):
        html = self._render(
            "format=html&service=signals"
            "&utm_source=moj_prop&utm_medium=onsite"
            "&utm_campaign=signals_education_lead_20261121"
            "&utm_content=signal_nav"
        )
        self.assertIn('<option value="signals" selected>', html)
        for name, value in (
            ("utm_source", "moj_prop"), ("utm_medium", "onsite"),
            ("utm_campaign", "signals_education_lead_20261121"),
            ("utm_content", "signal_nav"),
        ):
            self.assertIn('name="' + name + '" value="' + value + '"', html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertNotIn('href="/mojprop-starter30-checkout/"', html)

    def test_unreviewed_campaign_and_pii_never_echo(self):
        for q in (
            "format=html&service=signals&utm_campaign=evil-campaign",
            "format=html&service=signals&utm_source=moj_prop"
            "&utm_medium=onsite&utm_campaign=signals_education_lead_20261121"
            "&utm_content=PII-email%40example.invalid",
            "format=html&service=signals&utm_source=moj_prop"
            "&utm_source=moj_prop&utm_medium=onsite"
            "&utm_campaign=signals_education_lead_20261121"
            "&utm_content=signal_nav",
        ):
            with self.subTest(query=q):
                html = self._render(q)
                self.assertNotIn("evil-campaign", html)
                self.assertNotIn("PII-email", html)
                self.assertNotIn('name="utm_source"', html)
                self.assertNotIn('name="utm_campaign"', html)

    def test_unknown_source_does_not_gain_attribution_provenance(self):
        html = self._render(
            "format=html&service=signals&utm_source=paid_fake"
            "&utm_medium=onsite&utm_campaign=signals_education_lead_20261121"
            "&utm_content=signal_nav"
        )
        self.assertNotIn("paid_fake", html)
        self.assertNotIn('name="utm_source"', html)

    def test_generic_request_does_not_claim_a_verified_campaign(self):
        html = self._render(
            "format=html&utm_source=moj_prop&utm_medium=onsite"
            "&utm_campaign=signals_education_lead_20261121"
            "&utm_content=signal_nav"
        )
        self.assertNotIn('name="utm_campaign"', html)


if __name__ == "__main__":
    import unittest
    unittest.main()
