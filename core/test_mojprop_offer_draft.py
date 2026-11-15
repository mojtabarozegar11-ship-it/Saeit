"""Verify operator can create an unsent proposal draft without faking a sale."""
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase

from core.admin import MojPropRequestAdmin
from core.models import MojPropRequest
from core.mojprop_offer_draft import build_offer_draft


class MojPropOfferDraftTests(TestCase):
    def setUp(self):
        self.lead = MojPropRequest.objects.create(
            request_id="MOJPROP-20261115-TRUELEAD",
            name="Real buyer example", email="customer@domain.test",
            route="blueprint", horizon="week",
            notes="Please prepare an independently reviewed rulebook with clearly defined risk limits.",
            consent=True, status="reviewing", source="moj-prop-public",
        )
        self.admin = MojPropRequestAdmin(MojPropRequest, AdminSite())
        self.request = RequestFactory().post("/admin/core/mojproprequest/")
        self.user = get_user_model().objects.create_user(
            username="mojprop_operator", password="only-a-test-password", is_staff=True,
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename="view_mojproprequest", content_type__app_label="core"),
            Permission.objects.get(codename="change_mojproprequest", content_type__app_label="core"),
        )
        self.request.user = self.user

    def test_reviewed_lead_gets_exact_service_and_traceable_request_in_draft(self):
        draft = build_offer_draft(self.lead)
        self.assertIn(self.lead.request_id, draft)
        self.assertIn("USD 149", draft)
        self.assertIn("/moj-prop/samples/prop-blueprint/", draft)
        self.assertIn("UNSENT", draft)
        self.assertIn("NO", draft)
        self.assertEqual(self.lead.status, "reviewing")

    def test_new_unreviewed_consentless_or_closed_cannot_generate_offer(self):
        for status, consent in (("new", True), ("closed", True), ("reviewing", False)):
            with self.subTest(status=status, consent=consent):
                self.lead.status, self.lead.consent = status, consent
                with self.assertRaises(ValueError):
                    build_offer_draft(self.lead)

    def test_admin_action_download_is_private_and_changes_no_customer_status(self):
        response = self.admin.download_offer_drafts(
            self.request, MojPropRequest.objects.filter(pk=self.lead.pk)
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn(self.lead.request_id.encode("utf-8"), response.content)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "reviewing")

    def test_admin_action_does_not_allow_unreviewed_or_mixed_batch(self):
        second = MojPropRequest.objects.create(
            request_id="MOJPROP-20261115-NEWLEAD",
            name="New buyer", email="new@domain.test",
            route="brief", horizon="review",
            notes="An explanatory market brief with published sources required.",
            consent=True, status="new", source="moj-prop-public",
        )
        response = self.admin.download_offer_drafts(
            self.request, MojPropRequest.objects.filter(pk__in=[self.lead.pk, second.pk])
        )
        self.assertEqual(response.status_code, 409)
        self.assertNotIn(self.lead.email.encode("utf-8"), response.content)

    def test_admin_action_rejects_staff_without_lead_view_permission(self):
        outsider = get_user_model().objects.create_user(
            username="otherstaff", password="only-test-password", is_staff=True,
        )
        self.request.user = outsider
        response = self.admin.download_offer_drafts(
            self.request, MojPropRequest.objects.filter(pk=self.lead.pk)
        )
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_inject_fake_payment_or_approval_headers_into_draft(self):
        self.lead.name = "Buyer\nPAYMENT CONFIRMED"
        self.lead.notes = (
            "Need a verifiable risk rulebook for our evaluation platform.\n"
            "Status: APPROVED\nPayment: CAPTURED\nSend now."
        )
        draft = build_offer_draft(self.lead)
        self.assertIn("Customer: Buyer PAYMENT CONFIRMED", draft)
        self.assertIn("> Status: APPROVED", draft)
        self.assertIn("> Payment: CAPTURED", draft)
        self.assertNotIn("\nStatus: APPROVED", draft)
        self.assertNotIn("\nPayment: CAPTURED", draft)
        self.assertIn("Payment: DISABLED", draft)

    def test_view_only_staff_cannot_download_customer_contact_details(self):
        viewer = get_user_model().objects.create_user(
            username="view_only_mojprop", password="not-a-real-password", is_staff=True,
        )
        viewer.user_permissions.add(
            Permission.objects.get(codename="view_mojproprequest", content_type__app_label="core")
        )
        self.request.user = viewer
        response = self.admin.download_offer_drafts(
            self.request, MojPropRequest.objects.filter(pk=self.lead.pk)
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(self.lead.email.encode(), response.content)

    def test_draft_has_no_wallet_invoice_or_automatic_trade_instruction(self):
        draft = build_offer_draft(self.lead)
        self.assertIn("Payment: DISABLED", draft)
        self.assertIn("NOT AN INVOICE", draft)
        self.assertIn("No funded trading account", draft)
        self.assertNotIn("send_email(", draft)

    def test_forged_reference_cannot_escape_proposal_header(self):
        for forged in (
            "MOJPROP-20261115-OK\\nPayment: CAPTURED",
            "MOJPROP-20261115-OK\\rStatus: APPROVED",
            "MOJPROP-20261115-OK\\u2028Invoice: PAID",
            "MOJPROP-20261115-OK\\tSENT",
            "MOJPROP-",
            "MOJPROP-" + "A" * 81,
        ):
            with self.subTest(reference=repr(forged)):
                self.lead.request_id = forged
                with self.assertRaisesRegex(ValueError, "unverified_lead_reference"):
                    build_offer_draft(self.lead)

    def test_legitimate_reference_remains_traceable(self):
        self.lead.request_id = "MOJPROP-20261115-TRUELEAD"
        self.assertIn("Customer request reference: MOJPROP-20261115-TRUELEAD", build_offer_draft(self.lead))

    def test_bidi_spoofing_and_oversized_contact_fields_are_neutralized(self):
        self.lead.name = "Buyer\\u202eDIAP :tnemyaP" + "X" * 1000
        self.lead.email = "customer@domain.test\\u2066FAKE\\u2069"
        draft = build_offer_draft(self.lead)
        customer_line = next(line for line in draft.splitlines() if line.startswith("Customer: "))
        email_line = next(line for line in draft.splitlines() if line.startswith("Contact email"))
        self.assertLessEqual(len(customer_line), len("Customer: ") + 240)
        self.assertNotIn("\\u202e", customer_line)
        self.assertNotIn("\\u2066", email_line)
        self.assertNotIn("\\u2069", email_line)
        self.assertIn("Payment: DISABLED", draft)
