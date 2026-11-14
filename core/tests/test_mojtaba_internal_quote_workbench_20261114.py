"""Private lead-to-quote workflow: isolated Django DB + HTTP regression suite.

No real customer contact, external payment, contract, release or deployment.
"""
import hashlib
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.company_inquiry_models import CompanyInquiry
from core.company_sales_intake import CompanySalesInquiryForm, FORM_VERSION
from core.company_quote_workflow import (
    CompanyReviewForm, CompanyDraftQuoteForm, DRAFT_ACTION, REVIEW_ACTION,
    SERVICE_BY_KIND, new_desk_token, review_company_inquiry,
    prepare_internal_quote, make_review_form, make_quote_form, case_drafts,
)
from core.company_sales_pipeline import sales_pipeline_snapshot
from core.economic_master_agent import EconomicMasterAgent
from core.models import AuditLog, Order, PaymentIntent


@override_settings(
    DEBUG=True, ALLOWED_HOSTS=["testserver", "zomorodmelal.ir", "mojplaywin.com"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    TRADE_EMAIL_ENABLED=False,
)
class PrivateQuoteWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser(
            username="crm-owner", email="owner@zomorodmelal.ir",
            password="not-a-live-secret",
        )
        self.staff = User.objects.create_user(
            username="crm-staff", password="not-a-live-secret",
            is_staff=True,
        )
        self.case = CompanyInquiry.objects.create(
            kind="commercial", name="Private Buyer",
            organization="An Agricultural Group",
            email="buyer@agri-business.org",
            phone="+989121234567",
            subject="Economics consulting needed",
            message="A farm economics feasibility scope with actual farm data.",
        )
        label = str(CompanySalesInquiryForm().fields["consent"].label)
        self.consent = AuditLog.objects.create(
            actor_type="visitor", actor_id="",
            action="company_inquiry_consent_submitted",
            target_type="CompanyInquiry", target_id=str(self.case.pk),
            trace_id=f"company-lead-{self.case.pk}",
            before_state={}, after_state={
                "form_version": FORM_VERSION,
                "consent_checked": True,
                "consent_text_sha256": hashlib.sha256(label.encode("utf-8")).hexdigest(),
                "purpose": "review_and_related_follow_up_only",
                "outbound_contact_sent": False,
                "sale_verified": False,
                "payment_accepted": False,
            },
        )
        self.service = "farm_economic_advisory"

    def review_data(self, **kwargs):
        self.case.refresh_from_db()
        return {
            "request_token": new_desk_token(),
            "revision": self.case.updated_at.isoformat(),
            "qualification": "eligible",
            "service_code": self.service,
            **kwargs,
        }

    def quote_data(self, **kwargs):
        self.case.refresh_from_db()
        return {
            "request_token": new_desk_token(),
            "revision": self.case.updated_at.isoformat(),
            "service_code": self.service,
            "currency": "IRT",
            "unit_price": "2500000.00",
            "quantity": "2",
            "turnaround_days": "30",
            "valid_days": "10",
            **kwargs,
        }

    def review(self, **kwargs):
        f = CompanyReviewForm(self.review_data(**kwargs), case_kind=self.case.kind)
        self.assertTrue(f.is_valid(), f.errors)
        return review_company_inquiry(case_id=self.case.pk, owner=self.owner, form=f)

    def quote(self, **kwargs):
        f = CompanyDraftQuoteForm(self.quote_data(**kwargs), case_kind=self.case.kind)
        self.assertTrue(f.is_valid(), f.errors)
        return prepare_internal_quote(case_id=self.case.pk, owner=self.owner, form=f)

    def review_url(self):
        return reverse("mojtaba_company_case_action", args=[self.case.pk, "review"])

    def quote_url(self):
        return reverse("mojtaba_company_case_action", args=[self.case.pk, "draft"])

    def detail_url(self):
        return reverse("mojtaba_company_case_detail", args=[self.case.pk])

    def test_01_list_denies_anonymous(self):
        r = self.client.get("/staff/command-center/sales-cases/")
        self.assertEqual(r.status_code, 403)

    def test_02_list_denies_staff_nonowner(self):
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.get("/staff/command-center/sales-cases/").status_code, 403,
        )

    def test_03_detail_denies_staff_nonowner(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.detail_url()).status_code, 403)

    def test_04_action_denies_staff_nonowner(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(self.review_url(), self.review_data()).status_code, 403)

    def test_05_owner_list_shows_real_database_record(self):
        self.client.force_login(self.owner)
        r = self.client.get("/staff/command-center/sales-cases/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.case.subject)

    def test_06_owner_detail_shows_requested_scope_privately(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.detail_url()), self.case.message)

    def test_07_owner_only_views_no_store_noindex(self):
        self.client.force_login(self.owner)
        for path in (self.detail_url(), "/staff/command-center/sales-cases/"):
            r = self.client.get(path)
            self.assertIn("no-store", r["Cache-Control"])
            self.assertIn("noindex", r["X-Robots-Tag"])

    def test_08_owner_only_on_company_domain(self):
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(self.detail_url(), HTTP_HOST="mojplaywin.com").status_code,
            404,
        )

    def test_09_owner_list_paginated(self):
        for i in range(26):
            CompanyInquiry.objects.create(
                kind="research", name="Another User", email=f"buyer{i}@agri.org",
                subject=f"Inquiry {i}", message="Real scope to review later",
            )
        self.client.force_login(self.owner)
        first = self.client.get("/staff/command-center/sales-cases/")
        second = self.client.get("/staff/command-center/sales-cases/?page=2")
        self.assertEqual(len(first.context["items"]), 25)
        self.assertEqual(len(second.context["items"]), 2)

    def test_10_detail_contains_real_csrf(self):
        self.client.force_login(self.owner)
        r = self.client.get(self.detail_url())
        self.assertContains(r, 'name="csrfmiddlewaretoken"')

    def test_11_owner_action_denies_get(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.review_url()).status_code, 405)

    def test_12_owner_action_rejects_invalid_operation(self):
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.post(
                reverse("mojtaba_company_case_action", args=[self.case.pk, "send"]),
                self.review_data(),
            ).status_code, 404,
        )

    def test_13_csrf_blocks_review_post(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.owner)
        self.assertEqual(c.post(self.review_url(), self.review_data()).status_code, 403)
        self.assertFalse(AuditLog.objects.filter(action=REVIEW_ACTION).exists())

    def test_14_review_moves_new_to_reviewing(self):
        event = self.review()
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, "reviewing")
        self.assertEqual(event.action, REVIEW_ACTION)

    def test_15_review_records_owner_identity_and_no_contact(self):
        event = self.review()
        self.assertEqual(event.actor_type, "owner")
        self.assertEqual(event.actor_id, str(self.owner.pk))
        self.assertIs(event.after_state["customer_contacted"], False)

    def test_16_review_is_not_contract_or_payment(self):
        event = self.review()
        self.assertFalse(event.after_state["legal_offer_accepted"])
        self.assertFalse(event.after_state["payment_collected"])

    def test_17_review_exact_replay_is_idempotent(self):
        data = self.review_data()
        f = CompanyReviewForm(data, case_kind="commercial")
        first = review_company_inquiry(case_id=self.case.pk, owner=self.owner, form=f)
        second = review_company_inquiry(case_id=self.case.pk, owner=self.owner, form=f)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(AuditLog.objects.filter(action=REVIEW_ACTION).count(), 1)

    def test_18_out_of_scope_closes_case(self):
        self.review(qualification="out_of_scope")
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, "closed")

    def test_19_closed_review_exact_replay_does_not_reopen(self):
        data = self.review_data(qualification="out_of_scope")
        f = CompanyReviewForm(data, case_kind="commercial")
        first = review_company_inquiry(case_id=self.case.pk, owner=self.owner, form=f)
        again = review_company_inquiry(case_id=self.case.pk, owner=self.owner, form=f)
        self.assertEqual(first.pk, again.pk)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, "closed")

    def test_20_closed_case_denies_new_review(self):
        self.review(qualification="out_of_scope")
        with self.assertRaises(ValidationError):
            self.review()

    def test_21_previously_approved_case_denies_internal_edit(self):
        self.case.status = "approved"; self.case.save(update_fields=["status", "updated_at"])
        with self.assertRaises(ValidationError):
            self.review()

    def test_22_missing_consent_denies_review(self):
        self.consent.delete()
        with self.assertRaises(ValidationError):
            self.review()

    def test_23_wrong_consent_version_denies_review(self):
        self.consent.after_state = {**self.consent.after_state, "form_version": "old"}
        self.consent.save(update_fields=["after_state"])
        with self.assertRaises(ValidationError):
            self.review()

    def test_24_wrong_consent_digest_denies_review(self):
        self.consent.after_state = {**self.consent.after_state, "consent_text_sha256": "0"*64}
        self.consent.save(update_fields=["after_state"])
        with self.assertRaises(ValidationError):
            self.review()

    def test_25_unchecked_consent_denies_review(self):
        self.consent.after_state = {**self.consent.after_state, "consent_checked": False}
        self.consent.save(update_fields=["after_state"])
        with self.assertRaises(ValidationError):
            self.review()

    def test_26_wrong_purpose_denies_review(self):
        self.consent.after_state = {**self.consent.after_state, "purpose": "marketing"}
        self.consent.save(update_fields=["after_state"])
        with self.assertRaises(ValidationError):
            self.review()

    def test_27_wrong_kind_service_denied_by_form(self):
        f = CompanyReviewForm(self.review_data(service_code="greenhouse_feasibility"), case_kind="commercial")
        self.assertFalse(f.is_valid())

    def test_28_wrong_kind_service_denied_at_workflow_too(self):
        f = CompanyReviewForm(self.review_data(service_code="greenhouse_feasibility"))
        self.assertTrue(f.is_valid())
        with self.assertRaises(ValidationError):
            review_company_inquiry(case_id=self.case.pk, owner=self.owner, form=f)

    def test_29_stale_revision_denies_review(self):
        data = self.review_data()
        self.case.status = "reviewing"
        self.case.save(update_fields=["status", "updated_at"])
        f = CompanyReviewForm(data, case_kind="commercial")
        with self.assertRaises(ValidationError):
            review_company_inquiry(case_id=self.case.pk, owner=self.owner, form=f)

    def test_30_missing_form_token_denied(self):
        f = CompanyReviewForm(self.review_data(request_token="foo"), case_kind="commercial")
        self.assertFalse(f.is_valid())

    def test_31_regular_staff_cannot_call_review_service(self):
        f = CompanyReviewForm(self.review_data(), case_kind="commercial")
        with self.assertRaises(PermissionDenied):
            review_company_inquiry(case_id=self.case.pk, owner=self.staff, form=f)

    def test_32_no_quote_before_qualifying_review(self):
        with self.assertRaises(ValidationError):
            self.quote()

    def test_33_insufficient_review_blocks_quote(self):
        self.review(qualification="needs_details")
        with self.assertRaises(ValidationError):
            self.quote()

    def test_34_closed_case_blocks_quote(self):
        self.review(qualification="out_of_scope")
        with self.assertRaises(ValidationError):
            self.quote()

    def test_35_good_review_makes_internal_quote(self):
        self.review()
        e = self.quote()
        self.assertEqual(e.action, DRAFT_ACTION)
        self.assertEqual(e.after_state["status"], "internal_draft")

    def test_36_quote_amount_math_is_exact_decimal(self):
        self.review()
        e = self.quote()
        self.assertEqual(e.after_state["gross_total"], "5000000.00")
        self.assertEqual(e.after_state["currency"], "IRT")

    def test_37_quote_is_private_and_nonbinding(self):
        self.review()
        e = self.quote()
        self.assertTrue(e.after_state["private_and_nonbinding"])
        self.assertFalse(e.after_state["customer_delivery_authorized"])
        self.assertFalse(e.after_state["invoice_issued"])
        self.assertIsNone(e.after_state["cash_collected"])

    def test_38_quote_never_changes_order_or_customer_status(self):
        self.review()
        self.quote()
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, "reviewing")
        self.assertFalse(Order.objects.exists())
        self.assertFalse(PaymentIntent.objects.exists())

    def test_39_quote_does_not_send_email(self):
        self.review()
        with patch("django.core.mail.send_mail", side_effect=AssertionError("no send")):
            with patch("smtplib.SMTP.sendmail", side_effect=AssertionError("no SMTP")):
                self.quote()

    def test_40_duplicate_quote_token_creates_one_draft(self):
        self.review()
        data = self.quote_data()
        f = CompanyDraftQuoteForm(data, case_kind="commercial")
        first = prepare_internal_quote(case_id=self.case.pk, owner=self.owner, form=f)
        again = prepare_internal_quote(case_id=self.case.pk, owner=self.owner, form=f)
        self.assertEqual(first.pk, again.pk)
        self.assertEqual(AuditLog.objects.filter(action=DRAFT_ACTION).count(), 1)

    def test_41_new_quote_token_creates_new_internal_revision(self):
        self.review()
        self.quote()
        self.quote(unit_price="3000000.00")
        self.assertEqual(AuditLog.objects.filter(action=DRAFT_ACTION).count(), 2)

    def test_42_price_cannot_be_zero(self):
        self.review()
        f = CompanyDraftQuoteForm(self.quote_data(unit_price="0"), case_kind="commercial")
        self.assertFalse(f.is_valid())

    def test_43_negative_price_denied(self):
        self.review()
        f = CompanyDraftQuoteForm(self.quote_data(unit_price="-12"), case_kind="commercial")
        self.assertFalse(f.is_valid())

    def test_44_nonfinite_price_denied(self):
        self.review()
        f = CompanyDraftQuoteForm(self.quote_data(unit_price="NaN"), case_kind="commercial")
        self.assertFalse(f.is_valid())

    def test_45_invalid_currency_denied(self):
        self.review()
        f = CompanyDraftQuoteForm(self.quote_data(currency="MOJ"), case_kind="commercial")
        self.assertFalse(f.is_valid())

    def test_46_fractional_quantity_denied(self):
        self.review()
        f = CompanyDraftQuoteForm(self.quote_data(quantity="1.2"), case_kind="commercial")
        self.assertFalse(f.is_valid())

    def test_47_total_over_guard_rejected(self):
        self.review()
        with self.assertRaises(ValidationError):
            self.quote(unit_price="9999999999.99", quantity="12")

    def test_48_turnaround_outside_range_denied(self):
        self.review()
        f = CompanyDraftQuoteForm(self.quote_data(turnaround_days="0"), case_kind="commercial")
        self.assertFalse(f.is_valid())

    def test_49_valid_days_outside_range_denied(self):
        self.review()
        f = CompanyDraftQuoteForm(self.quote_data(valid_days="999"), case_kind="commercial")
        self.assertFalse(f.is_valid())

    def test_50_quote_service_must_match_latest_review(self):
        self.review()
        with self.assertRaises(ValidationError):
            self.quote(service_code="supply_chain_economics")

    def test_51_quote_invalidated_by_manual_case_edit(self):
        self.review()
        self.case.refresh_from_db()
        self.case.subject = "New independent request scope"
        self.case.save(update_fields=["subject", "updated_at"])
        with self.assertRaises(ValidationError):
            self.quote()

    def test_52_quote_owner_only_service_call(self):
        self.review()
        form = CompanyDraftQuoteForm(self.quote_data(), case_kind="commercial")
        with self.assertRaises(PermissionDenied):
            prepare_internal_quote(case_id=self.case.pk, owner=self.staff, form=form)

    def test_53_quote_contains_no_customer_pii_in_audit(self):
        self.review()
        e = self.quote()
        combined = str(e.after_state) + str(e.before_state)
        self.assertNotIn(self.case.email, combined)
        self.assertNotIn(self.case.message, combined)
        self.assertNotIn(self.case.name, combined)

    def test_54_quote_list_from_real_audit_records(self):
        self.review()
        self.quote()
        self.assertEqual(len(case_drafts(self.case.pk)), 1)

    def test_55_quote_count_visible_without_contact_details(self):
        self.review()
        self.quote()
        overview = sales_pipeline_snapshot()
        self.assertEqual(overview["internal_nonbinding_quote_drafts"], 1)
        self.assertTrue(overview["drafts_are_not_sales"])
        self.assertIsNone(overview["settled_cash"])

    def test_56_single_bot_consumes_same_draft_metric(self):
        self.review()
        self.quote()
        overview = EconomicMasterAgent().inspect_sales_pipeline_readonly()
        self.assertEqual(overview["bot_id"], "mojtaba.bot.ai")
        self.assertEqual(overview["internal_nonbinding_quote_drafts"], 1)

    def test_57_valid_owner_post_review_redirects_detail(self):
        self.client.force_login(self.owner)
        r = self.client.post(self.review_url(), self.review_data())
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], self.detail_url())

    def test_58_valid_owner_post_quote_creates_actual_audit(self):
        self.review()
        self.client.force_login(self.owner)
        r = self.client.post(self.quote_url(), self.quote_data())
        self.assertEqual(r.status_code, 302)
        self.assertEqual(AuditLog.objects.filter(action=DRAFT_ACTION).count(), 1)

    def test_59_nonqualifying_owner_post_returns_conflict(self):
        self.client.force_login(self.owner)
        r = self.client.post(self.quote_url(), self.quote_data())
        self.assertEqual(r.status_code, 409)
        self.assertFalse(AuditLog.objects.filter(action=DRAFT_ACTION).exists())

    def test_60_invalid_owner_post_returns_422_without_write(self):
        self.client.force_login(self.owner)
        r = self.client.post(self.review_url(), self.review_data(request_token="bad"))
        self.assertEqual(r.status_code, 422)
        self.assertFalse(AuditLog.objects.filter(action=REVIEW_ACTION).exists())

    def test_61_oversize_post_gets_413(self):
        self.client.force_login(self.owner)
        r = self.client.post(self.review_url(), {**self.review_data(), "padding": "x" * 5000})
        self.assertEqual(r.status_code, 413)

    def test_62_owner_post_is_private_no_store(self):
        self.client.force_login(self.owner)
        r = self.client.post(self.review_url(), self.review_data())
        self.assertIn("no-store", r["Cache-Control"])

    def test_63_no_automatic_customer_reply_or_payment(self):
        self.client.force_login(self.owner)
        self.client.post(self.review_url(), self.review_data())
        self.client.post(self.quote_url(), self.quote_data())
        self.assertEqual(AuditLog.objects.filter(action=DRAFT_ACTION).count(), 1)
        self.assertFalse(Order.objects.exists())

    def test_64_public_site_cannot_access_owner_quote(self):
        self.client.force_login(self.owner)
        r = self.client.post(self.quote_url(), self.quote_data(), HTTP_HOST="mojplaywin.com")
        self.assertEqual(r.status_code, 404)

    def test_65_review_from_one_kind_cannot_price_another(self):
        self.case.kind = "research"
        self.case.save(update_fields=["kind", "updated_at"])
        valid = SERVICE_BY_KIND["research"][0][0]
        self.review(service_code=valid)
        f = CompanyDraftQuoteForm(self.quote_data(service_code="farm_economic_advisory"), case_kind="research")
        self.assertFalse(f.is_valid())

    def test_66_replay_review_with_changed_qualification_is_denied(self):
        data = self.review_data()
        f = CompanyReviewForm(data, case_kind="commercial")
        review_company_inquiry(case_id=self.case.pk, owner=self.owner, form=f)
        changed = CompanyReviewForm(
            {**data, "qualification": "out_of_scope"}, case_kind="commercial"
        )
        with self.assertRaises(ValidationError):
            review_company_inquiry(
                case_id=self.case.pk, owner=self.owner, form=changed
            )
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, "reviewing")

    def test_67_replay_quote_token_with_changed_price_is_denied(self):
        self.review()
        data = self.quote_data()
        first = CompanyDraftQuoteForm(data, case_kind="commercial")
        prepare_internal_quote(case_id=self.case.pk, owner=self.owner, form=first)
        changed = CompanyDraftQuoteForm(
            {**data, "unit_price": "3000000.00"}, case_kind="commercial"
        )
        with self.assertRaises(ValidationError):
            prepare_internal_quote(
                case_id=self.case.pk, owner=self.owner, form=changed
            )
        self.assertEqual(AuditLog.objects.filter(action=DRAFT_ACTION).count(), 1)

    def test_68_review_digest_excludes_pii(self):
        event = self.review()
        self.assertEqual(len(event.after_state["action_digest"]), 64)
        self.assertNotIn(self.case.email, str(event.after_state))

    def test_69_quote_digest_matches_after_exact_replay(self):
        self.review()
        data = self.quote_data()
        f = CompanyDraftQuoteForm(data, case_kind="commercial")
        first = prepare_internal_quote(case_id=self.case.pk, owner=self.owner, form=f)
        again = prepare_internal_quote(case_id=self.case.pk, owner=self.owner, form=f)
        self.assertEqual(first.after_state["action_digest"], again.after_state["action_digest"])
