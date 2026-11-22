"""CRM lead-quality regression tests for the public company inquiry form."""

from django.test import TestCase
from django.urls import reverse

from core.company_inquiry_models import CompanyInquiry


class CompanyInquiryValidationTests(TestCase):
    def payload(self):
        return {
            "kind": "commercial",
            "name": "Customer",
            "organization": "Partner",
            "email": "customer@example.org",
            "phone": "",
            "subject": "Request a quotation",
            "message": "Please tell me about the available service.",
            "privacy_consent": "on",
        }

    def submit(self, payload):
        response = self.client.post(reverse("company"), data=payload)
        self.assertEqual(response.status_code, 302)
        return response

    def test_valid_inquiry_creates_one_lead(self):
        self.submit(self.payload())
        self.assertEqual(CompanyInquiry.objects.count(), 1)
        inquiry = CompanyInquiry.objects.get()
        self.assertEqual(inquiry.status, "new")
        self.assertEqual(inquiry.email, "customer@example.org")

    def test_invalid_email_does_not_create_lead(self):
        payload = self.payload()
        payload["email"] = "not-an-email"
        self.submit(payload)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_unlisted_inquiry_kind_does_not_create_lead(self):
        payload = self.payload()
        payload["kind"] = "unknown-kind"
        self.submit(payload)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_overlong_subject_does_not_create_lead(self):
        payload = self.payload()
        payload["subject"] = "x" * 301
        self.submit(payload)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_oversized_message_does_not_create_lead(self):
        payload = self.payload()
        payload["message"] = "x" * 5001
        self.submit(payload)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_missing_required_name_does_not_create_lead(self):
        payload = self.payload()
        payload["name"] = " "
        self.submit(payload)
        self.assertFalse(CompanyInquiry.objects.exists())


    def test_no_consent_never_creates_a_lead(self):
        p = self.payload()
        del p["privacy_consent"]
        self.submit(p)
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_refusal_of_consent_does_not_create_a_lead(self):
        p = self.payload()
        p["privacy_consent"] = ""
        self.submit(p)
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_hidden_bot_field_is_rejected(self):
        p = self.payload()
        p["website"] = "https://spam.example"
        self.submit(p)
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_identical_rapid_repeat_creates_one_inquiry(self):
        p = self.payload()
        self.submit(p)
        self.submit(p)
        self.assertEqual(CompanyInquiry.objects.count(), 1)

    def test_distinct_subject_is_not_suppressed(self):
        p = self.payload()
        self.submit(p)
        p["subject"] = "A different service question"
        self.submit(p)
        self.assertEqual(CompanyInquiry.objects.count(), 2)

    def test_email_is_normalized_in_saved_record(self):
        p = self.payload()
        p["email"] = "  CUSTOMER@Example.org  "
        self.submit(p)
        self.assertEqual(CompanyInquiry.objects.count(), 1)
        self.assertEqual(CompanyInquiry.objects.get().email, "CUSTOMER@example.org")

    def test_consent_event_is_stamped_in_internal_record(self):
        self.submit(self.payload())
        i = CompanyInquiry.objects.get()
        self.assertIn("C19_PRIVACY_CONSENT_V1", i.internal_note)
        self.assertNotIn("customer@example.org", i.internal_note)

    def test_oversize_body_declared_is_blocked_before_form_parse(self):
        payload = self.payload()
        payload["message"] = "x" * 31000
        response = self.client.post(reverse("company"), data=payload)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_company_template_has_unchecked_consent_and_no_auto_send(self):
        page = self.client.get(reverse("company")).content.decode("utf-8")
        self.assertIn('name="privacy_consent"', page)
        self.assertIn('name="website"', page)
        self.assertIn('type="checkbox"', page)
        self.assertIn("required", page)
        self.assertNotIn('name="privacy_consent" checked', page)
        self.assertNotIn("fetch('/company/'", page)
