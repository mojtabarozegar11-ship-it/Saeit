"""Django acceptance tests for the public Moj Prop applicant endpoint."""
from __future__ import annotations

import json

from django.test import TestCase
from django.urls import reverse

from prop_firm.models import PropApplicant
from prop_firm.public_intake import CONSENT_VERSION, RISK_DISCLOSURE_VERSION


class MojPropPublicApplicantEndpointTests(TestCase):
    def setUp(self):
        self.url = reverse("moj_prop_public_applicant_intake")
        self.payload = {
            "email": "Buyer@example.com",
            "preferred_language": "fa",
            "jurisdiction": "CA",
            "source": "mojtaba.bot.ai",
            "consent_version": CONSENT_VERSION,
            "risk_disclosure_version": RISK_DISCLOSURE_VERSION,
            "risk_acknowledged": True,
        }

    def post_json(self, payload=None):
        return self.client.post(
            self.url,
            data=json.dumps(payload if payload is not None else self.payload),
            content_type="application/json",
        )

    def test_get_is_not_an_intake_method(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(PropApplicant.objects.count(), 0)

    def test_invalid_lead_is_not_persisted(self):
        payload = dict(self.payload)
        payload["consent_version"] = "old"
        response = self.post_json(payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["accepted"], False)
        self.assertEqual(PropApplicant.objects.count(), 0)

    def test_valid_lead_is_persisted_without_money_movement(self):
        response = self.post_json()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["accepted"])
        self.assertTrue(body["persisted"])
        self.assertTrue(body["created"])
        self.assertFalse(body["checkout_enabled"])
        self.assertFalse(body["trading_enabled"])
        self.assertFalse(body["payout_enabled"])
        self.assertNotIn("buyer@example.com", response.content.decode().lower())
        applicant = PropApplicant.objects.get()
        self.assertEqual(applicant.email, "buyer@example.com")
        self.assertEqual(applicant.status, PropApplicant.Status.NEW)

    def test_duplicate_email_is_idempotent(self):
        first = self.post_json()
        second = self.post_json()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["created"])
        self.assertEqual(PropApplicant.objects.count(), 1)

    def test_truthy_integer_does_not_acknowledge_risk(self):
        payload = dict(self.payload)
        payload["risk_acknowledged"] = 1
        response = self.post_json(payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PropApplicant.objects.count(), 0)

    def test_oversized_body_is_rejected(self):
        payload = dict(self.payload)
        payload["jurisdiction"] = "x" * 10000
        response = self.post_json(payload)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(PropApplicant.objects.count(), 0)
