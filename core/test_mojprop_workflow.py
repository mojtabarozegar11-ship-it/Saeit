"""Actual admin form and workflow safeguards for real customer leads."""
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.admin import MojPropRequestAdmin, MojPropRequestStatusForm
from core.models import MojPropRequest
from core.mojprop_workflow import validate_status_change


class MojPropCommercialStageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = MojPropRequest.objects.create(
            request_id="MOJPROP-20261115-CRM01",
            name="Verified Example Customer", email="buyer@valid-domain.tld",
            route="blueprint", horizon="week",
            notes="Document the program governance and risk rules.",
            consent=True, source="moj-prop-public", status="new",
        )

    def form(self, status, note=""):
        return MojPropRequestStatusForm(
            data={"status": status, "internal_note": note},
            instance=MojPropRequest.objects.get(pk=self.customer.pk),
        )

    def test_new_request_can_enter_review_without_fabricated_offer(self):
        form = self.form("reviewing")
        self.assertTrue(form.is_valid(), form.errors)

    def test_new_request_cannot_skip_review_straight_to_sale(self):
        for step in ("offer_sent", "approved", "delivered"):
            with self.subTest(step=step):
                self.assertFalse(self.form(step, "OFFER: fake reference").is_valid())

    def test_written_offer_requires_documented_reference(self):
        MojPropRequest.objects.filter(pk=self.customer.pk).update(status="reviewing")
        self.assertFalse(self.form("offer_sent", "I sent it").is_valid())
        self.assertTrue(self.form(
            "offer_sent", "OFFER: signed-proposal/MOJPROP-20261115-CRM01/v1",
        ).is_valid())

    def test_acceptance_needs_separate_customer_evidence(self):
        MojPropRequest.objects.filter(pk=self.customer.pk).update(status="offer_sent")
        self.assertFalse(self.form("approved", "OFFER: proposal only").is_valid())
        self.assertTrue(self.form(
            "approved", "ACCEPTANCE: email-approval-archived-20261115-CRM01",
        ).is_valid())

    def test_previous_offer_reference_cannot_be_erased_when_customer_accepts(self):
        previous = "OFFER: proposal/MOJPROP-20261115-CRM01/v1"
        MojPropRequest.objects.filter(pk=self.customer.pk).update(
            status="offer_sent", internal_note=previous
        )
        self.assertFalse(self.form(
            "approved", "ACCEPTANCE: customer-approval-archive/20261115-CRM01"
        ).is_valid())
        self.assertTrue(self.form(
            "approved",
            previous + "\nACCEPTANCE: customer-approval-archive/20261115-CRM01"
        ).is_valid())

    def test_historical_delivery_evidence_cannot_be_overwritten_in_same_status(self):
        evidence = "OFFER: signed-proposal/MOJPROP-20261115-CRM01/v1"
        MojPropRequest.objects.filter(pk=self.customer.pk).update(
            status="offer_sent", internal_note=evidence
        )
        self.assertFalse(self.form("offer_sent", "").is_valid())
        self.assertTrue(self.form("offer_sent", evidence).is_valid())

    def test_delivery_needs_documented_evidence(self):
        MojPropRequest.objects.filter(pk=self.customer.pk).update(status="approved")
        self.assertFalse(self.form("delivered", "finished").is_valid())
        self.assertTrue(self.form(
            "delivered", "DELIVERY: archive/delivery-confirmation-MOJPROP-CRM01",
        ).is_valid())

    def test_terminal_states_cannot_be_automatically_reopened(self):
        for state in ("spam", "closed"):
            with self.subTest(state=state):
                with self.assertRaises(ValidationError):
                    validate_status_change(state, "approved", "ACCEPTANCE: fabricated")

    def test_admin_never_creates_unsolicited_customer_leads(self):
        admin = MojPropRequestAdmin(MojPropRequest, AdminSite())
        self.assertFalse(admin.has_add_permission(None))
        self.assertIn("consent", admin.readonly_fields)
        self.assertIn("notes", admin.readonly_fields)
        self.assertIn("email", admin.readonly_fields)

    def test_operator_cannot_delete_customer_evidence_or_consented_request(self):
        admin = MojPropRequestAdmin(MojPropRequest, AdminSite())
        self.assertFalse(admin.has_delete_permission(None))
        self.assertFalse(admin.has_delete_permission(None, self.customer))
        self.assertTrue(MojPropRequest.objects.filter(pk=self.customer.pk).exists())

    def test_review_transition_records_operator_review_time(self):
        admin = MojPropRequestAdmin(MojPropRequest, AdminSite())
        lead = MojPropRequest.objects.get(pk=self.customer.pk)
        lead.status = "reviewing"
        self.assertIsNone(lead.reviewed_at)
        admin.save_model(None, lead, None, True)
        lead.refresh_from_db()
        self.assertEqual(lead.status, "reviewing")
        self.assertIsNotNone(lead.reviewed_at)

    def test_viewing_same_status_does_not_require_new_evidence(self):
        self.assertTrue(self.form("new").is_valid())
        self.assertEqual(self.customer.status, "new")
