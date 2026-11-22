"""Preserve only allowlisted, *client-declared* Signal Desk campaign on CRM leads.

Offline database-isolated Django tests; never access owner production,
collect real customer data, publish social posts, email or charge 30 TRX.
"""
from urllib.parse import urlencode
from django.http import QueryDict
from django.test import SimpleTestCase, TestCase
from core.models import MojPropRequest
from core.mojprop_views import _allowlisted_self_declared_lead_source


CAMPAIGN = {
    "utm_source": "moj_prop",
    "utm_medium": "onsite",
    "utm_campaign": "signals_education_lead_20261121",
    "utm_content": "signal_nav",
}
LABEL = "moj-prop-public:signals_education_lead_20261121"


class SafeCampaignSourceLabelTests(SimpleTestCase):
    def test_01_exactly_allowlisted_signals_tuple_gets_bounded_label(self):
        result = _allowlisted_self_declared_lead_source(CAMPAIGN, "signals")
        self.assertEqual(result, LABEL)
        self.assertLessEqual(len(result), 80)

    def test_02_none_or_missing_campaign_is_legacy_default(self):
        for payload in (None, {}, {"utm_source": "moj_prop"}):
            with self.subTest(payload=payload):
                self.assertEqual(
                    _allowlisted_self_declared_lead_source(payload, "signals"),
                    "moj-prop-public",
                )

    def test_03_untrusted_or_extra_tracking_fields_are_not_persisted(self):
        for mutation in (
            {"utm_campaign": "invented_campaign"},
            {"utm_source": "attacker"},
            {"utm_medium": "paid_click"},
            {"utm_content": "attacker@example.invalid"},
            {"utm_extra": "unreviewed-value"},
        ):
            with self.subTest(mutation=mutation):
                payload = {**CAMPAIGN, **mutation}
                self.assertEqual(
                    _allowlisted_self_declared_lead_source(payload, "signals"),
                    "moj-prop-public",
                )

    def test_04_other_product_routes_never_inherit_signal_campaign(self):
        for service in ("blueprint", "brief", "digital", "audit", "", "invalid"):
            with self.subTest(service=service):
                self.assertEqual(
                    _allowlisted_self_declared_lead_source(CAMPAIGN, service),
                    "moj-prop-public",
                )

    def test_05_duplicate_querystring_is_not_promoted_to_approved_source(self):
        query = QueryDict(urlencode(CAMPAIGN) + "&utm_campaign=attacker_campaign")
        self.assertEqual(
            _allowlisted_self_declared_lead_source(query, "signals"),
            "moj-prop-public",
        )

    def test_06_duplicate_even_if_same_value_is_rejected(self):
        query = QueryDict(urlencode(CAMPAIGN) + "&utm_source=moj_prop")
        self.assertEqual(
            _allowlisted_self_declared_lead_source(query, "signals"),
            "moj-prop-public",
        )

    def test_07_unsupported_non_string_campaign_never_gets_persisted(self):
        for value in (None, 1, [], {"x": 1}, True):
            with self.subTest(value=value):
                payload = {**CAMPAIGN, "utm_content": value}
                self.assertEqual(
                    _allowlisted_self_declared_lead_source(payload, "signals"),
                    "moj-prop-public",
                )

    def test_08_cannot_echo_pii_or_set_paid_status_or_reward_entitlement(self):
        source = _allowlisted_self_declared_lead_source(
            {**CAMPAIGN, "name": "Private Name",
             "email": "private@example.invalid",
             "receipt_token": "private_bearer_token"},
            "signals",
        )
        self.assertEqual(source, LABEL)
        self.assertNotIn("Private", source)
        self.assertNotIn("@", source)
        self.assertNotIn("paid", source.lower())
        self.assertNotIn("reward", source.lower())


class CampaignSourceCRMWriteIntegrationTests(TestCase):
    """A Django test database is created by the test runner, not owner MariaDB."""

    def _post(self, extra=None, route="signals", suffix="01"):
        data = {
            "name": "Fictional Test Prospect",
            "email": "fictional-prospect-" + suffix + "@samplebusiness.com",
            "service": route,
            "horizon": "review",
            "notes": "Please share educational market brief service scope.",
            "consent": "on",
            "website": "",
            **(extra or {}),
        }
        return self.client.post(
            "/moj-prop-intake/?format=html",
            data=urlencode(data),
            content_type="application/x-www-form-urlencoded",
        )

    def test_09_valid_allowlisted_consent_creates_unpaid_labelled_lead_only(self):
        before = MojPropRequest.objects.count()
        response = self._post(extra=CAMPAIGN)
        self.assertEqual(response.status_code, 201, response.content[:400])
        self.assertEqual(MojPropRequest.objects.count(), before + 1)
        lead = MojPropRequest.objects.order_by("-pk").first()
        self.assertEqual(lead.source, LABEL)
        self.assertEqual(lead.route, "signals")
        self.assertEqual(lead.status, "new")
        self.assertTrue(lead.consent)

    def test_10_untrusted_campaign_still_accepts_customer_without_attribution(self):
        response = self._post(
            extra={**CAMPAIGN, "utm_campaign": "injected-non-campaign"},
            suffix="02",
        )
        self.assertEqual(response.status_code, 201, response.content[:400])
        lead = MojPropRequest.objects.order_by("-pk").first()
        self.assertEqual(lead.source, "moj-prop-public")
        self.assertEqual(lead.status, "new")

    def test_11_non_signal_services_keep_original_source(self):
        response = self._post(extra=CAMPAIGN, route="brief", suffix="03")
        self.assertEqual(response.status_code, 201, response.content[:400])
        lead = MojPropRequest.objects.order_by("-pk").first()
        self.assertEqual(lead.source, "moj-prop-public")
        self.assertEqual(lead.route, "brief")

    def test_12_identical_retry_does_not_create_second_or_rewrite_attribution(self):
        import uuid
        key = str(uuid.uuid4())
        before = MojPropRequest.objects.count()
        response1 = self._post(extra={**CAMPAIGN, "idempotency_key": key}, suffix="04")
        self.assertEqual(response1.status_code, 201, response1.content[:400])
        response2 = self._post(extra={"idempotency_key": key}, suffix="04")
        self.assertEqual(response2.status_code, 200, response2.content[:400])
        self.assertEqual(MojPropRequest.objects.count(), before + 1)
        lead = MojPropRequest.objects.order_by("-pk").first()
        self.assertEqual(lead.source, LABEL)
        self.assertIn(b"original request was recovered", response2.content.lower())


    def test_13_staff_or_nonpublic_source_cannot_be_recovered_by_public_key(self):
        import uuid
        from core.mojprop_views import _keyed_request_id
        key = str(uuid.uuid4())
        MojPropRequest.objects.create(
            request_id=_keyed_request_id(key),
            name="Fictional Test Prospect",
            email="fictional-prospect-05@samplebusiness.com",
            route="signals",
            horizon="review",
            notes="Please share educational market brief service scope.",
            consent=True,
            source="staff-private-record",
        )
        response = self._post(extra={
            **CAMPAIGN, "idempotency_key": key,
        }, suffix="05")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(MojPropRequest.objects.count(), 1)
        self.assertEqual(
            MojPropRequest.objects.get(request_id=_keyed_request_id(key)).source,
            "staff-private-record",
        )
        self.assertNotIn(b"private-receipt", response.content)


if __name__ == "__main__":
    import unittest
    unittest.main()
