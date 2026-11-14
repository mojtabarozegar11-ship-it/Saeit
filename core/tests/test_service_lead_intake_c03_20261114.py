"""Isolated end-to-end nonbinding service lead intake, no emails/payments."""
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.company_inquiry_models import CompanyInquiry
from core.service_lead_views import MAX_POST_BYTES, _request_size_allowed
from core.service_sales_controls import SERVICE_CARDS


@override_settings(DEBUG=True)
class ServiceInquiryFlowTests(TestCase):
    def setUp(self):
        self.url = reverse("service_inquiry", kwargs={"service_code": "AGR-01"})
        self.payload = {
            "name": "Farm Customer",
            "organization": "Agriculture Group",
            "email": "Buyer@Example.COM",
            "phone": "",
            "subject": "Farm economics review",
            "message": (
                "We need a comprehensive farm profitability analysis including "
                "fixed and variable costs, sensitivity and delivery limitations."
            ),
            "consent": "on",
            "website": "",
        }

    def _post(self, **changes):
        data = dict(self.payload)
        data.update(changes)
        return self.client.post(self.url, data=data)

    def test_all_six_service_pages_have_real_descriptions(self):
        for code in SERVICE_CARDS:
            r = self.client.get(reverse("service_inquiry", args=[code]))
            self.assertEqual(r.status_code, 200, code)
            self.assertContains(r, SERVICE_CARDS[code]["title_fa"])

    def test_service_page_has_no_payment_gate(self):
        body = self.client.get(self.url).content.decode()
        self.assertIn("در این صفحه پرداخت انجام نمی‌شود", body)

    def test_service_page_requires_no_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_invalid_service_code_is_404(self):
        self.assertEqual(
            self.client.get(reverse("service_inquiry", args=["FAKE-99"])).status_code, 404
        )

    @override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com"])
    def test_never_offer_farsi_lead_page_on_mojplaywin(self):
        self.assertEqual(
            self.client.get(self.url, HTTP_HOST="mojplaywin.com").status_code, 404
        )

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_debug_test_host_rejected_in_production_mode(self):
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_existing_services_landing_links_six_real_service_codes(self):
        response = self.client.get(reverse("services"))
        self.assertEqual(response.status_code, 200)
        text = response.content.decode("utf-8")
        for code in SERVICE_CARDS:
            self.assertIn(reverse("service_inquiry", args=[code]), text)

    def test_valid_request_creates_exactly_one_lead(self):
        r = self._post()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CompanyInquiry.objects.count(), 1)

    def test_public_lead_initial_state_is_new_not_approved(self):
        self._post()
        self.assertEqual(CompanyInquiry.objects.get().status, "new")

    def test_service_code_prefixed_for_traceability(self):
        self._post()
        self.assertEqual(
            CompanyInquiry.objects.get().subject,
            "[AGR-01] Farm economics review",
        )

    def test_kind_is_derived_from_service_not_untrusted_post(self):
        self._post(kind="approved")
        self.assertEqual(CompanyInquiry.objects.get().kind, "project")

    def test_research_service_leads_are_research_kind(self):
        r = self.client.post(reverse("service_inquiry", args=["RS-01"]), self.payload)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CompanyInquiry.objects.get().kind, "research")

    def test_web_service_leads_are_commercial_kind(self):
        r = self.client.post(reverse("service_inquiry", args=["WEB-01"]), self.payload)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CompanyInquiry.objects.get().kind, "commercial")

    def test_email_is_canonical_lowercase(self):
        self._post()
        self.assertEqual(CompanyInquiry.objects.get().email, "buyer@example.com")

    def test_phone_is_optional(self):
        self._post(phone="")
        self.assertEqual(CompanyInquiry.objects.get().phone, "")

    def test_storage_note_records_consent_notice(self):
        self._post()
        note = CompanyInquiry.objects.get().internal_note
        self.assertIn("consent: checked", note)
        self.assertIn("nonbinding: true", note)

    def test_post_redirect_get_preserves_true_acknowledgement_once(self):
        self._post()
        first = self.client.get(self.url)
        self.assertTrue(first.context["received"])
        second = self.client.get(self.url)
        self.assertFalse(second.context["received"])

    def test_query_param_cannot_fabricate_received(self):
        response = self.client.get(self.url + "?submitted=1")
        self.assertFalse(response.context["received"])

    def test_duplicate_recent_submission_is_not_double_counted(self):
        self._post()
        self._post()
        self.assertEqual(CompanyInquiry.objects.count(), 1)

    def test_changed_message_is_a_distinct_request(self):
        self._post()
        self._post(message="A separate and different new request for soil input costs.")
        self.assertEqual(CompanyInquiry.objects.count(), 2)

    def test_old_identical_request_can_be_submitted_again(self):
        self._post()
        old = CompanyInquiry.objects.get()
        CompanyInquiry.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(hours=2)
        )
        self._post()
        self.assertEqual(CompanyInquiry.objects.count(), 2)

    def test_without_consent_no_lead_is_saved(self):
        response = self._post(consent="")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_invalid_email_does_not_create_lead(self):
        self._post(email="not-an-email")
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_whitespace_only_name_does_not_create_lead(self):
        self._post(name="    ")
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_short_subject_does_not_create_lead(self):
        self._post(subject="x")
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_short_message_does_not_create_lead(self):
        self._post(message="too short")
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_overlong_subject_is_rejected(self):
        self._post(subject="S" * 210)
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_overlong_message_is_rejected(self):
        self._post(message="M" * 3501)
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_honeypot_bot_is_rejected(self):
        self._post(website="https://spam.invalid/")
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_attachment_is_not_accepted(self):
        payload = dict(self.payload)
        payload["attachment"] = SimpleUploadedFile("secret.txt", b"private data")
        response = self.client.post(self.url, data=payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_unsupported_json_post_does_not_store(self):
        response = self.client.post(self.url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 415)
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_oversized_actual_request_body_is_blocked(self):
        response = self.client.generic(
            "POST", self.url, data="x" * (MAX_POST_BYTES + 100),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_declared_oversize_is_blocked_before_processing(self):
        from django.test import RequestFactory
        req = RequestFactory().post(self.url, data=self.payload)
        req.META["CONTENT_LENGTH"] = str(MAX_POST_BYTES + 1)
        self.assertFalse(_request_size_allowed(req))

    def test_malformed_declared_length_is_rejected(self):
        from django.test import RequestFactory
        req = RequestFactory().post(self.url, data=self.payload)
        req.META["CONTENT_LENGTH"] = "nonsense"
        self.assertFalse(_request_size_allowed(req))

    def test_put_is_not_accepted(self):
        self.assertEqual(self.client.put(self.url, data="test").status_code, 405)

    def test_no_store_and_nosniff_on_form(self):
        response = self.client.get(self.url)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_no_store_on_validation_errors(self):
        response = self._post(consent="")
        self.assertIn("no-store", response["Cache-Control"])

    def test_html_is_escaped_on_validation_error(self):
        response = self._post(
            name="<script>alert(1)</script>", consent=""
        )
        body = response.content.decode()
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_no_outbound_email_during_storage(self):
        with patch("django.core.mail.send_mail") as send:
            self._post()
        send.assert_not_called()

    def test_no_payment_or_order_is_created(self):
        from core.models import Order, PaymentIntent
        self._post()
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(PaymentIntent.objects.count(), 0)

    def test_missing_csrf_token_is_rejected_in_realistic_client(self):
        secured = Client(enforce_csrf_checks=True)
        response = secured.post(self.url, self.payload)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_valid_csrf_token_allows_submission(self):
        secured = Client(enforce_csrf_checks=True)
        page = secured.get(self.url)
        self.assertEqual(page.status_code, 200)
        payload = dict(self.payload)
        payload["csrfmiddlewaretoken"] = secured.cookies["csrftoken"].value
        response = secured.post(self.url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CompanyInquiry.objects.count(), 1)
