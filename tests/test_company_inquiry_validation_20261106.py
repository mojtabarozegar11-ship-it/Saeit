"""CRM lead-quality regression tests for the public company inquiry form."""

from django.test import TestCase
from django.urls import reverse

from core.company_inquiry_models import CompanyInquiry


class CompanyInquiryValidationTests(TestCase):
    def payload(self):
        return {
            "kind": "commercial",
            "consent": "yes",
            "website": "",
            "name": "Customer",
            "organization": "Partner",
            "email": "customer@example.org",
            "phone": "",
            "subject": "Request a quotation",
            "message": "Please tell me about the available service.",
        }

    def submit(self, payload, expected_status=302):
        response = self.client.post(reverse("company"), data=payload)
        self.assertEqual(response.status_code, expected_status)
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
        self.submit(payload, expected_status=400)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_unlisted_inquiry_kind_does_not_create_lead(self):
        payload = self.payload()
        payload["kind"] = "unknown-kind"
        self.submit(payload, expected_status=400)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_overlong_subject_does_not_create_lead(self):
        payload = self.payload()
        payload["subject"] = "x" * 301
        self.submit(payload, expected_status=400)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_oversized_message_does_not_create_lead(self):
        payload = self.payload()
        payload["message"] = "x" * 5001
        self.submit(payload, expected_status=400)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_missing_required_name_does_not_create_lead(self):
        payload = self.payload()
        payload["name"] = " "
        self.submit(payload, expected_status=400)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_valid_name_and_organization_whitespace_normalized(self):
        payload = self.payload()
        payload["name"] = "  Customer   Example "
        payload["organization"] = "  Farm  Group "
        self.submit(payload)
        lead = CompanyInquiry.objects.get()
        self.assertEqual(lead.name, "Customer Example")
        self.assertEqual(lead.organization, "Farm Group")

    def test_email_domain_normalized_but_local_part_preserved(self):
        payload = self.payload()
        payload["email"] = "Buyer@EXAMPLE.ORG"
        self.submit(payload)
        self.assertEqual(CompanyInquiry.objects.get().email, "Buyer@example.org")

    def test_bidi_control_in_subject_not_accepted(self):
        payload = self.payload()
        payload["subject"] = "Important\u202eFake"
        self.submit(payload, expected_status=400)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_invalid_phone_not_accepted(self):
        payload = self.payload()
        payload["phone"] = "+98-call-me"
        self.submit(payload, expected_status=400)
        self.assertFalse(CompanyInquiry.objects.exists())
