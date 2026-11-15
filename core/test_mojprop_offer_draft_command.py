"""Tests for the read-only Moj Prop offer-draft operator path."""
from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from core.mojprop_offer_draft import build_offer_draft


class MojPropOfferDraftCommandTests(SimpleTestCase):
    @staticmethod
    def lead(**overrides):
        values = {
            "pk": 17,
            "status": "reviewing",
            "consent": True,
            "request_id": "MOJPROP-20261115-A1B2C3D4",
            "name": "Mojtaba Rozegar",
            "email": "buyer@example.com",
            "route": "signals",
            "notes": "Prepare an educational gold-market brief with invalidation and risk limits.",
            "get_horizon_display": lambda: "This week",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_command_prints_a_traceable_draft_without_side_effect_markers(self):
        lead = self.lead()
        output = StringIO()
        with patch(
            "core.management.commands.mojprop_offer_draft.MojPropRequest.objects.filter"
        ) as query:
            query.return_value.first.return_value = lead
            call_command(
                "mojprop_offer_draft",
                request_id=lead.request_id,
                stdout=output,
            )

        text = output.getvalue()
        self.assertIn("UNSENT COMMERCIAL OFFER DRAFT", text)
        self.assertIn(lead.request_id, text)
        self.assertIn("Educational signal plan: NOT SELECTED", text)
        self.assertNotIn("Indicative starting amount: USD 29", text)
        self.assertIn("confirm the current catalog", text)
        self.assertIn("Payment: DISABLED", text)
        self.assertNotIn("send_mail(", text)
        self.assertNotIn("PaymentIntent.objects.create", text)

    def test_helper_rejects_a_new_lead_before_manual_review(self):
        lead = self.lead(status="new")
        with self.assertRaisesRegex(ValueError, "real_consent_and_operator_review_required"):
            build_offer_draft(lead)

    def test_helper_rejects_a_lead_without_explicit_consent(self):
        lead = self.lead(consent=False)
        with self.assertRaisesRegex(ValueError, "real_consent_and_operator_review_required"):
            build_offer_draft(lead)

    def test_command_does_not_accept_an_arbitrary_reference(self):
        output = StringIO()
        with self.assertRaises(Exception):
            call_command(
                "mojprop_offer_draft",
                request_id="not-a-mojprop-id",
                stdout=output,
            )
