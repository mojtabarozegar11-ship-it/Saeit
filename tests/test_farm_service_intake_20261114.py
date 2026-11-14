"""Django DB regressions for a real service-specific request using the same CRM.

Executable only with Django + a configured test DB; NEVER imply these were
run merely because the source file is committed.
"""
from django.test import TestCase
from django.urls import reverse

from core.company_inquiry_models import CompanyInquiry


class FarmServiceIntakeTests(TestCase):
    def path(self):
        return reverse("farm_economics_request")

    def payload(self):
        return {
            "kind": "research",  # server must refuse tampered classification
            "subject": "other subject chosen by browser",
            "name": "Farm owner", "organization": "Farm A",
            "email": "owner@example.org", "phone": "",
            "message": "We need a twelve month cashflow review for two crops.",
            "consent": "yes", "website": "",
        }

    def test_get_shows_server_rendered_usable_form(self):
        page = self.client.get(self.path())
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'action="/company/farm-economics/request/"')
        self.assertContains(page, 'name="csrfmiddlewaretoken"')
        self.assertContains(page, 'name="consent"')

    def test_get_never_creates_fake_crm_lead(self):
        self.client.get(self.path())
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_real_post_creates_one_farm_crm_lead(self):
        response = self.client.post(self.path(), self.payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CompanyInquiry.objects.count(), 1)
        lead = CompanyInquiry.objects.get()
        self.assertEqual(lead.kind, "commercial")
        self.assertEqual(lead.subject, "ZM-FARM | درخواست تحلیل اقتصادی مزرعه")
        self.assertEqual(lead.email, "owner@example.org")

    def test_valid_request_generates_private_receipt(self):
        response = self.client.post(self.path(), self.payload())
        self.assertIn("/company/receipt/", response["Location"])
        page = self.client.get(response["Location"])
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "owner@example.org")

    def test_missing_explicit_consent_rejected(self):
        data = self.payload()
        data.pop("consent")
        response = self.client.post(self.path(), data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_invalid_form_renders_same_farm_route_to_retry(self):
        data = self.payload()
        data["email"] = "bad-email"
        response = self.client.post(self.path(), data)
        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response, 'action="/company/farm-economics/request/"', status_code=400,
        )
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_same_session_duplicate_does_not_create_two_records(self):
        first = self.client.post(self.path(), self.payload())
        second = self.client.post(self.path(), self.payload())
        self.assertEqual(first["Location"], second["Location"])
        self.assertEqual(CompanyInquiry.objects.count(), 1)

    def test_non_get_post_methods_are_denied(self):
        self.assertEqual(self.client.put(self.path(), data="").status_code, 405)

    def test_bot_honeypot_cannot_create_lead(self):
        data = self.payload()
        data["website"] = "spam.example"
        self.assertEqual(self.client.post(self.path(), data).status_code, 400)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_no_payment_is_created_by_intake(self):
        response = self.client.post(self.path(), self.payload())
        self.assertEqual(response.status_code, 302)
        lead = CompanyInquiry.objects.get()
        self.assertEqual(lead.status, "new")
        self.assertFalse(hasattr(lead, "paid_amount"))
