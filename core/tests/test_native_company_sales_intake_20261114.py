"""Native lead intake: real Django DB/HTTP tests, no external communications."""
from datetime import timedelta
from io import StringIO
import json
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils import timezone

from core.company_inquiry_models import CompanyInquiry
from core.company_sales_intake import (
    CompanySalesInquiryForm, validate_body_size, require_company_host,
)
from core.company_sales_pipeline import sales_pipeline_snapshot
from core.economic_master_agent import EconomicMasterAgent


@override_settings(
    DEBUG=True,
    ALLOWED_HOSTS=["testserver", "zomorodmelal.ir", "mojplaywin.com"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    TRADE_EMAIL_ENABLED=False,
)
class NativeCompanySalesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser(
            username="sales-owner", email="owner@zomorodmelal.ir",
            password="offline-only",
        )
        self.staff = User.objects.create_user(
            username="sales-staff", password="offline-only", is_staff=True,
        )
        self.buyer_data = {
            "kind": "commercial",
            "name": "Ali Customer",
            "organization": "Farm Cooperative",
            "email": "buyer@agricultural-services.org",
            "phone": "+989121234567",
            "subject": "Farm profit optimization quote",
            "message": "Please provide a proposal for farm economics consultation.",
            "consent": "on",
            "website": "",
        }

    def payload(self, **kw):
        return {**self.buyer_data, **kw}

    def post(self, *, endpoint="/contact/", **changes):
        return self.client.post(
            endpoint, self.payload(**changes),
            HTTP_HOST="zomorodmelal.ir",
        )

    def assert_rejected(self, **changes):
        r = self.post(**changes)
        self.assertEqual(r.status_code, 422, r.content[:300])
        self.assertEqual(CompanyInquiry.objects.count(), 0)
        return r

    def test_01_native_contact_get_is_rendered(self):
        self.assertEqual(self.client.get("/contact/", HTTP_HOST="zomorodmelal.ir").status_code, 200)

    def test_02_native_form_has_csrf(self):
        r = self.client.get("/contact/", HTTP_HOST="zomorodmelal.ir")
        self.assertContains(r, 'name="csrfmiddlewaretoken"')

    def test_03_native_form_explains_nonbinding_terms(self):
        r = self.client.get("/contact/", HTTP_HOST="zomorodmelal.ir")
        self.assertContains(r, "این فرم قرارداد")

    def test_04_native_form_discloses_information_use(self):
        r = self.client.get("/contact/", HTTP_HOST="zomorodmelal.ir")
        self.assertContains(r, "برای بررسی همین استعلام")

    def test_05_native_form_honeypot_hidden(self):
        r = self.client.get("/contact/", HTTP_HOST="zomorodmelal.ir")
        self.assertContains(r, 'name="website"')

    def test_06_valid_lead_is_persisted_in_existing_crm(self):
        self.assertEqual(self.post().status_code, 302)
        self.assertEqual(CompanyInquiry.objects.count(), 1)

    def test_07_valid_lead_starts_at_new_only(self):
        self.post()
        item = CompanyInquiry.objects.get()
        self.assertEqual(item.status, "new")
        self.assertEqual(item.internal_note, "")

    def test_08_email_domain_normalized(self):
        self.post(email="Buyer@Agricultural-Services.ORG")
        self.assertEqual(
            CompanyInquiry.objects.get().email, "Buyer@agricultural-services.org",
        )

    def test_09_receipt_session_flag_only_after_db_save(self):
        self.post()
        r = self.client.get("/contact/", HTTP_HOST="zomorodmelal.ir")
        self.assertContains(r, "فرم شما در سامانهٔ داخلی شرکت ثبت شد.")

    def test_10_receipt_is_not_issued_from_query_string(self):
        r = self.client.get("/contact/?received=1", HTTP_HOST="zomorodmelal.ir")
        self.assertNotContains(r, "فرم شما در سامانهٔ داخلی شرکت ثبت شد.")

    def test_11_receipt_flash_one_time_only(self):
        self.post()
        self.client.get("/contact/", HTTP_HOST="zomorodmelal.ir")
        r = self.client.get("/contact/", HTTP_HOST="zomorodmelal.ir")
        self.assertNotContains(r, "فرم شما در سامانهٔ داخلی شرکت ثبت شد.")

    def test_12_no_automatic_email(self):
        with patch("django.core.mail.send_mail", side_effect=AssertionError("must not send")):
            self.assertEqual(self.post().status_code, 302)

    def test_13_no_order_created(self):
        from core.models import Order
        self.post()
        self.assertFalse(Order.objects.exists())

    def test_14_missing_consent_rejected(self):
        self.assert_rejected(consent="")

    def test_15_forged_consent_rejected(self):
        self.assert_rejected(consent="false")

    def test_16_honeypot_rejected(self):
        self.assert_rejected(website="https://spam.example")

    def test_17_invalid_email_rejected(self):
        self.assert_rejected(email="broken-email")

    def test_18_placeholder_email_rejected(self):
        self.assert_rejected(email="bot@localhost")

    def test_19_invalid_domain_rejected(self):
        self.assert_rejected(email="bot@spam.invalid")

    def test_20_email_newline_rejected(self):
        self.assert_rejected(email="buyer@agri.org\nbcc:attacker")

    def test_21_missing_name_rejected(self):
        self.assert_rejected(name=" ")

    def test_22_one_character_name_rejected(self):
        self.assert_rejected(name="x")

    def test_23_multiline_name_rejected(self):
        self.assert_rejected(name="Ali\nUser")

    def test_24_unlisted_category_rejected(self):
        self.assert_rejected(kind="free-money")

    def test_25_subject_too_short_rejected(self):
        self.assert_rejected(subject="x")

    def test_26_subject_crlf_rejected(self):
        self.assert_rejected(subject="Quote request\nBCC: spam")

    def test_27_message_too_short_rejected(self):
        self.assert_rejected(message="Hi")

    def test_28_message_too_long_rejected(self):
        self.assert_rejected(message="a"*5001)

    def test_29_message_with_spam_links_rejected(self):
        self.assert_rejected(message="Open https://a.co then https://b.co and https://c.co for spam.")

    def test_30_phone_injection_rejected(self):
        self.assert_rejected(phone="not a phone; DROP TABLE")

    def test_31_phone_is_optional(self):
        self.assertEqual(self.post(phone="").status_code, 302)

    def test_32_organization_is_optional(self):
        self.assertEqual(self.post(organization="").status_code, 302)

    def test_33_duplicate_same_inquiry_is_prevented(self):
        self.assertEqual(self.post().status_code, 302)
        self.assertEqual(self.post().status_code, 422)
        self.assertEqual(CompanyInquiry.objects.count(), 1)

    def test_34_limit_fourth_request_in_one_hour(self):
        for n in range(3):
            self.assertEqual(
                self.post(subject=f"Independent quote {n}", message=f"Request {n}: advise about farm output forecasting.").status_code,
                302,
            )
        r = self.post(subject="Independent quote 4", message="Independent fourth farm economics request.")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(CompanyInquiry.objects.count(), 3)

    def test_35_company_legacy_form_requires_consent(self):
        self.assert_rejected(endpoint="/company/", consent="")

    def test_36_company_legacy_valid_still_persists(self):
        r = self.post(endpoint="/company/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CompanyInquiry.objects.count(), 1)

    def test_37_contact_rejects_wrong_site(self):
        r = self.client.get("/contact/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(r.status_code, 404)

    def test_38_wrong_site_cannot_submit_crm(self):
        r = self.client.post("/contact/", self.payload(), HTTP_HOST="mojplaywin.com")
        self.assertEqual(r.status_code, 404)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_39_contact_get_no_cache(self):
        r = self.client.get("/contact/", HTTP_HOST="zomorodmelal.ir")
        self.assertIn("no-store", r["Cache-Control"])
        self.assertIn("noindex", r["X-Robots-Tag"])

    def test_40_contact_rejects_unintended_put(self):
        r = self.client.put("/contact/", {}, HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(r.status_code, 405)

    def test_41_real_csrf_enforcement(self):
        client = Client(enforce_csrf_checks=True)
        r = client.post("/contact/", self.payload(), HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_42_intake_does_not_touch_paid_status(self):
        r = self.post()
        self.assertEqual(r.status_code, 302)
        self.assertNotEqual(CompanyInquiry.objects.get().status, "approved")

    def test_43_overlong_body_declined_preparse(self):
        request = RequestFactory().post("/contact/", self.payload(), HTTP_HOST="zomorodmelal.ir")
        request.META["CONTENT_LENGTH"] = "14001"
        from django import forms
        with self.assertRaises(forms.ValidationError):
            validate_body_size(request)

    def test_44_active_owner_can_view_aggregate_crm(self):
        self.post()
        self.client.force_login(self.owner)
        r = self.client.get("/staff/command-center/api/bot/sales-pipeline/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["inquiries_received"], 1)

    def test_45_anonymous_cannot_view_aggregate(self):
        r = self.client.get("/staff/command-center/api/bot/sales-pipeline/")
        self.assertEqual(r.status_code, 403)

    def test_46_staff_cannot_view_aggregate(self):
        self.client.force_login(self.staff)
        r = self.client.get("/staff/command-center/api/bot/sales-pipeline/")
        self.assertEqual(r.status_code, 403)

    def test_47_aggregate_does_not_return_contact_identity(self):
        self.post()
        self.client.force_login(self.owner)
        r = self.client.get("/staff/command-center/api/bot/sales-pipeline/")
        raw = r.content.decode()
        self.assertNotIn("buyer@agricultural-services.org", raw)
        self.assertNotIn("Ali Customer", raw)

    def test_48_aggregate_is_not_a_revenue_claim(self):
        self.post()
        data = sales_pipeline_snapshot()
        self.assertIsNone(data["settled_cash"])
        self.assertIsNone(data["verified_profit"])
        self.assertIsNone(data["quote_accepted"])
        self.assertFalse(data["automatic_contact_enabled"])

    def test_49_aggregate_open_aging_tracks_48h(self):
        self.post()
        inquiry = CompanyInquiry.objects.get()
        CompanyInquiry.objects.filter(pk=inquiry.pk).update(
            created_at=timezone.now() - timedelta(days=3),
        )
        self.assertEqual(sales_pipeline_snapshot()["new_older_than_48h_requires_review"], 1)

    def test_50_aggregate_counts_status_and_category(self):
        self.post()
        result = sales_pipeline_snapshot()
        self.assertEqual(result["status_counts"], {"new": 1})
        self.assertEqual(result["kind_counts"], {"commercial": 1})

    def test_51_aggregate_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            sales_pipeline_snapshot(days=0)

    def test_52_aggregate_bool_window_rejected(self):
        with self.assertRaises(ValueError):
            sales_pipeline_snapshot(days=True)

    def test_53_aggregate_does_not_mutate_database(self):
        self.post()
        count = CompanyInquiry.objects.count()
        sales_pipeline_snapshot()
        self.assertEqual(CompanyInquiry.objects.count(), count)

    def test_54_owner_admin_can_review_leads(self):
        req = RequestFactory().get("/admin/core/companyinquiry/")
        req.user = self.owner
        model_admin = admin.site._registry[CompanyInquiry]
        self.assertTrue(model_admin.has_view_permission(req))

    def test_55_staff_admin_cannot_review_leads(self):
        req = RequestFactory().get("/admin/core/companyinquiry/")
        req.user = self.staff
        model_admin = admin.site._registry[CompanyInquiry]
        self.assertFalse(model_admin.has_view_permission(req))
        self.assertFalse(model_admin.has_change_permission(req))

    def test_56_crm_delete_disabled_even_for_owner(self):
        req = RequestFactory().get("/admin/core/companyinquiry/")
        req.user = self.owner
        self.assertFalse(admin.site._registry[CompanyInquiry].has_delete_permission(req))

    def test_57_read_only_cli_counts_same_records(self):
        self.post()
        stream = StringIO()
        call_command("mojtaba_sales_pipeline_readonly", stdout=stream)
        data = json.loads(stream.getvalue())
        self.assertEqual(data["inquiries_received"], 1)

    def test_58_master_agent_reads_same_actual_crm(self):
        self.post()
        data = EconomicMasterAgent().inspect_sales_pipeline_readonly()
        self.assertEqual(data["inquiries_received"], 1)
        self.assertEqual(data["bot_id"], "mojtaba.bot.ai")

    def test_59_aggregate_owner_get_private_no_store(self):
        self.client.force_login(self.owner)
        r = self.client.get("/staff/command-center/api/bot/sales-pipeline/")
        self.assertIn("no-store", r["Cache-Control"])

    def test_60_aggregate_post_disallowed(self):
        self.client.force_login(self.owner)
        r = self.client.post("/staff/command-center/api/bot/sales-pipeline/", {})
        self.assertEqual(r.status_code, 405)
