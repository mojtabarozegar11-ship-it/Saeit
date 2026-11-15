"""Moj Prop lead triage must not rewrite fulfilled or offered customer cases."""
from unittest.mock import patch
from django.contrib import admin
from django.test import RequestFactory, TestCase
from .admin import start_mojprop_review
from .models import MojPropRequest


class MojPropAdminTriageTests(TestCase):
    def make_lead(self, ref, status="new"):
        return MojPropRequest.objects.create(
            request_id=ref, name="Qualified buyer", email=f"{ref.lower()}@example.org",
            route="blueprint", horizon="urgent",
            notes="Request a reviewable written prop-rulebook proposal.",
            status=status, consent=True, source="moj-prop-public",
        )

    def test_claims_only_new_leads_and_stamps_time(self):
        new = self.make_lead("MOJPROP-ADMIN-001")
        offered = self.make_lead("MOJPROP-ADMIN-002", "offer_sent")
        request = RequestFactory().post("/admin/core/mojproprequest/")
        modeladmin = admin.site._registry[MojPropRequest]
        with patch.object(modeladmin, "message_user") as notify:
            start_mojprop_review(
                modeladmin, request, MojPropRequest.objects.filter(pk__in=[new.pk, offered.pk])
            )
        new.refresh_from_db()
        offered.refresh_from_db()
        self.assertEqual(new.status, "reviewing")
        self.assertIsNotNone(new.reviewed_at)
        self.assertEqual(offered.status, "offer_sent")
        self.assertIsNone(offered.reviewed_at)
        notify.assert_called_once()

    def test_second_claim_cannot_rewrite_review_time(self):
        lead = self.make_lead("MOJPROP-ADMIN-003")
        request = RequestFactory().post("/admin/core/mojproprequest/")
        modeladmin = admin.site._registry[MojPropRequest]
        with patch.object(modeladmin, "message_user"):
            start_mojprop_review(modeladmin, request, MojPropRequest.objects.all())
            lead.refresh_from_db()
            initial_time = lead.reviewed_at
            start_mojprop_review(modeladmin, request, MojPropRequest.objects.all())
        lead.refresh_from_db()
        self.assertEqual(lead.status, "reviewing")
        self.assertEqual(lead.reviewed_at, initial_time)
