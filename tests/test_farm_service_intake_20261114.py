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

    def test_consent_provenance_is_recorded_in_existing_crm(self):
        response = self.client.post(self.path(), self.payload())
        self.assertEqual(response.status_code, 302)
        record = CompanyInquiry.objects.get()
        self.assertIn("INTAKE_CONSENT_V1;", record.internal_note)
        self.assertIn("source=farm", record.internal_note)
        self.assertNotIn("owner@example.org", record.internal_note)

    def test_six_distinct_requests_in_session_seventh_is_rate_limited(self):
        for n in range(6):
            data = self.payload()
            data["message"] = f"Distinct scope of agricultural project {n}"
            self.assertEqual(self.client.post(self.path(), data).status_code, 302)
        data = self.payload()
        data["message"] = "Distinct scope of agricultural project 7"
        response = self.client.post(self.path(), data)
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)
        self.assertEqual(CompanyInquiry.objects.count(), 6)

    def test_replaying_existing_request_does_not_consume_new_lead_quota(self):
        first = self.client.post(self.path(), self.payload())
        for _ in range(7):
            response = self.client.post(self.path(), self.payload())
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], first["Location"])
        self.assertEqual(CompanyInquiry.objects.count(), 1)

    def test_a_b_a_replay_preserves_first_record(self):
        a = self.payload()
        b = self.payload()
        b["message"] = "Completely separate livestock enterprise"
        first = self.client.post(self.path(), a)
        second = self.client.post(self.path(), b)
        replay = self.client.post(self.path(), a)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(replay.status_code, 302)
        self.assertEqual(first["Location"], replay["Location"])
        self.assertEqual(CompanyInquiry.objects.count(), 2)

    def test_fingerprint_is_explicit_sha256(self):
        from core.company_content_views import CompanyInquiryForm, _inquiry_fingerprint
        form = CompanyInquiryForm(self.payload())
        self.assertTrue(form.is_valid())
        fp = _inquiry_fingerprint(form.cleaned_data)
        self.assertRegex(fp, r"^[0-9a-f]{64}$")

    def test_spoofed_generic_company_subject_is_not_farm_source(self):
        from core.company_inquiry_policy import provenance
        data = self.payload()
        data["kind"] = "commercial"
        data["subject"] = "ZM-FARM | درخواست تحلیل اقتصادی مزرعه"
        response = self.client.post(reverse("company"), data)
        self.assertEqual(response.status_code, 302)
        record = CompanyInquiry.objects.get()
        self.assertFalse(provenance(record.kind, record.subject, record.internal_note))
        self.assertIn("source=company", record.internal_note)

    def test_farm_source_is_counted_only_with_server_consent_marker(self):
        from core.company_inquiry_policy import provenance
        response = self.client.post(self.path(), self.payload())
        self.assertEqual(response.status_code, 302)
        record = CompanyInquiry.objects.get()
        self.assertTrue(provenance(record.kind, record.subject, record.internal_note))
