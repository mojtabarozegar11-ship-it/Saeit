"""Django ORM acceptance for an actual permission-gated admin triage operation.

These tests require a Django test DB. They do not verify a production host.
"""
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from core.admin import CompanyInquiryAdmin
from core.company_inquiry_models import CompanyInquiry


class CompanyInquiryAdminTriageTests(TestCase):
    def lead(self, status="new"):
        return CompanyInquiry.objects.create(
            kind="commercial", name="Customer", organization="Agribusiness",
            email="client@example.org", phone="",
            subject="ZM-FARM | درخواست تحلیل اقتصادی مزرعه",
            message="Review my farm accounts", status=status,
            internal_note="INTAKE_CONSENT_V1; confirmed_at=2026-11-14T12:00:00+00:00; source=farm",
        )

    def apply(self):
        site = AdminSite(name="staff")
        controller = CompanyInquiryAdmin(CompanyInquiry, site)
        request = RequestFactory().post("/admin/core/companyinquiry/")
        with patch.object(controller, "message_user") as notice:
            controller.begin_review(request, CompanyInquiry.objects.all())
        return notice

    def test_new_leads_enter_reviewing(self):
        row = self.lead()
        self.apply()
        row.refresh_from_db()
        self.assertEqual(row.status, "reviewing")

    def test_approved_leads_not_reopened(self):
        row = self.lead(status="approved")
        self.apply()
        row.refresh_from_db()
        self.assertEqual(row.status, "approved")

    def test_closed_leads_remain_closed(self):
        row = self.lead(status="closed")
        self.apply()
        row.refresh_from_db()
        self.assertEqual(row.status, "closed")

    def test_mixed_queryset_updates_only_new(self):
        self.lead(status="new")
        self.lead(status="reviewing")
        self.lead(status="approved")
        self.lead(status="closed")
        self.apply()
        self.assertEqual(CompanyInquiry.objects.filter(status="reviewing").count(), 2)
        self.assertEqual(CompanyInquiry.objects.filter(status="approved").count(), 1)
        self.assertEqual(CompanyInquiry.objects.filter(status="closed").count(), 1)

    def test_customer_identity_not_mutated_by_admin_action(self):
        row = self.lead()
        self.apply()
        row.refresh_from_db()
        self.assertEqual(row.email, "client@example.org")
        self.assertEqual(row.message, "Review my farm accounts")
        self.assertNotIn("PAYMENT_RECEIVED", row.internal_note)

    def test_admin_action_reports_real_updated_count(self):
        self.lead(status="new")
        self.lead(status="closed")
        notice = self.apply()
        self.assertTrue(notice.called)
        self.assertIn("1", str(notice.call_args))
