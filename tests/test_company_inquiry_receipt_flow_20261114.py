"""Real Django ORM/browser-client regression scenarios for stored CRM receipts.

These cases require a compatible Django app DB; creating the tests is not
evidence they were executed on the production MariaDB database.
"""
from django.core import signing
from django.test import Client, TestCase
from django.urls import reverse

from core.company_inquiry_models import CompanyInquiry
from core.company_inquiry_receipts import issue_receipt, verify_receipt


class InquiryReceiptFlowTests(TestCase):
    def payload(self):
        return {
            "kind": "commercial", "name": "Customer", "organization": "Farm",
            "email": "customer@example.org", "phone": "",
            "subject": "Farm economics quote request",
            "message": "Please review the feasibility of this farm enterprise.",
            "consent": "yes", "website": "",
        }

    def submit(self, data=None, client=None):
        return (client or self.client).post(reverse("company"), data=data or self.payload())

    def test_signed_receipt_created_after_real_db_save(self):
        response = self.submit()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CompanyInquiry.objects.count(), 1)
        self.assertIn("/company/receipt/", response["Location"])
        self.assertEqual(self.client.get(response["Location"]).status_code, 200)

    def test_customer_can_check_coarse_status(self):
        response = self.submit()
        self.assertContains(self.client.get(response["Location"]), "درخواست دریافت شد")
        CompanyInquiry.objects.update(status="reviewing")
        self.assertContains(self.client.get(response["Location"]), "در حال بررسی")

    def test_receipt_status_never_exposes_customer_pii(self):
        response = self.submit()
        page = self.client.get(response["Location"])
        self.assertNotContains(page, "customer@example.org")
        self.assertNotContains(page, "Customer")
        self.assertNotContains(page, "feasibility of this farm")
        self.assertNotContains(page, "12345")

    def test_receipt_status_not_a_payment_confirmation(self):
        response = self.submit()
        page = self.client.get(response["Location"])
        self.assertContains(page, "فاکتور یا تأیید دریافت وجه نیست")

    def test_receipt_cache_and_search_index_denied(self):
        response = self.submit()
        page = self.client.get(response["Location"])
        self.assertIn("no-store", page["Cache-Control"])
        self.assertEqual(page["Referrer-Policy"], "no-referrer")
        self.assertIn("noindex", page["X-Robots-Tag"])

    def test_forged_receipt_is_not_valid(self):
        self.submit()
        self.assertEqual(self.client.get("/company/receipt/forged-string/").status_code, 404)

    def test_nonexistent_signed_receipt_not_valid(self):
        path = reverse("company_inquiry_receipt", kwargs={"ticket": issue_receipt(987654321)})
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_unsigned_receipt_verification_rejected(self):
        from django.http import Http404
        with self.assertRaises(Http404):
            verify_receipt("1:fake")
        with self.assertRaises(Http404):
            verify_receipt(None)

    def test_valid_receipt_id_recoverable_but_no_user_details(self):
        self.submit()
        record = CompanyInquiry.objects.get()
        token = issue_receipt(record.pk)
        self.assertEqual(verify_receipt(token), record.pk)
        self.assertNotIn("customer@", token)

    def test_get_only_status_endpoint(self):
        response = self.submit()
        self.assertEqual(self.client.post(response["Location"], {}).status_code, 405)

    def test_missing_consent_retains_input_and_does_not_save(self):
        data = self.payload()
        data.pop("consent")
        response = self.submit(data)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Farm economics quote request", status_code=400)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_honeypot_blocks_submissions(self):
        data = self.payload()
        data["website"] = "https://spam.example"
        self.assertEqual(self.submit(data).status_code, 400)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_invalid_email_returns_correctable_form(self):
        data = self.payload()
        data["email"] = "invalid-email"
        page = self.submit(data)
        self.assertEqual(page.status_code, 400)
        self.assertContains(page, "invalid-email", status_code=400)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_empty_name_does_not_create_lead(self):
        data = self.payload()
        data["name"] = " "
        self.assertEqual(self.submit(data).status_code, 400)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_duplicate_post_in_single_session_uses_one_crm_record(self):
        first = self.submit()
        second = self.submit()
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(first["Location"], second["Location"])
        self.assertEqual(CompanyInquiry.objects.count(), 1)

    def test_changed_request_in_same_session_creates_distinct_lead(self):
        self.submit()
        data = self.payload()
        data["subject"] = "Separate project and quotation"
        self.submit(data)
        self.assertEqual(CompanyInquiry.objects.count(), 2)

    def test_two_independent_sessions_do_not_silently_merge_customers(self):
        first, second = Client(), Client()
        self.submit(client=first)
        self.submit(client=second)
        self.assertEqual(CompanyInquiry.objects.count(), 2)

    def test_original_crm_admin_workflow_still_exists(self):
        self.submit()
        record = CompanyInquiry.objects.get()
        self.assertEqual(record.kind, "commercial")
        self.assertEqual(record.status, "new")
        self.assertEqual(record.email, "customer@example.org")

    def test_closed_status_not_confused_with_refund(self):
        response = self.submit()
        CompanyInquiry.objects.update(status="closed")
        page = self.client.get(response["Location"])
        self.assertContains(page, "بسته شده")
        self.assertNotContains(page, "دریافت وجه انجام شد")

    def test_approval_status_not_confused_with_contract(self):
        response = self.submit()
        CompanyInquiry.objects.update(status="approved")
        self.assertContains(self.client.get(response["Location"]), "نه قرارداد یا پرداخت")

    def test_long_or_invalid_signing_payload_denied(self):
        from django.http import Http404
        with self.assertRaises(Http404):
            verify_receipt("a" * 500)
        forged = signing.dumps({"v": 2, "id": 1}, salt="core.company-inquiry.receipt.v1")
        with self.assertRaises(Http404):
            verify_receipt(forged)

    def test_removed_lead_receipt_does_not_expose_data(self):
        response = self.submit()
        CompanyInquiry.objects.all().delete()
        self.assertEqual(self.client.get(response["Location"]).status_code, 404)
