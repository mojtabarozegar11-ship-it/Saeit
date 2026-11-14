"""CRM lead-quality regression tests for the public company inquiry form."""

from django.test import TestCase, override_settings
from django.urls import reverse

from core.company_inquiry_models import CompanyInquiry


@override_settings(ALLOWED_HOSTS=["zomorodmelal.ir"], DEBUG=True)
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
            "consent": "on",
        }

    def submit(self, payload, *, expected_status=422):
        response = self.client.post(reverse("company"), data=payload)
        self.assertEqual(response.status_code, expected_status)
        return response

    def test_valid_inquiry_creates_one_lead(self):
        self.submit(self.payload(), expected_status=302)
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
