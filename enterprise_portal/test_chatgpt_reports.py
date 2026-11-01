
"""Private text-report route regressions; no live network, chat API or financial posting."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import BusinessUnit, ChatGPTActionReport

User = get_user_model()


@override_settings(COMPANY_OFFICE_REQUIRE_MFA=False, DEBUG=False, ALLOWED_HOSTS=["testserver"])
class ChatGPTTextReportTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username="reports-chief", password="reports-test-only",
            email="chief@example.org",
        )
        self.staff = User.objects.create_user(
            username="reports-staff", password="reports-test-only", is_staff=True,
        )
        self.unit = BusinessUnit.objects.create(code="zm-reports", name="مدیریت زمرد")
        self.url = "/company/office/chatgpt-reports/"

    def receipt(self, **overrides):
        data = dict(
            unit=self.unit, report_code="05-0004", cycle_code="05",
            run_reference="github-actions-41338335989",
            occurred_at=timezone.now(), title="ثبت اصلاحات واقعی",
            body="کد و آزمون ثبت شد؛ انتشار زنده تأیید نشده است.",
            outcome="partial", recorded_by=self.root,
            evidence_url="https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41338335989",
        )
        data.update(overrides)
        return ChatGPTActionReport.objects.create(**data)

    def test_page_requires_authenticated_superuser_even_with_view_permission(self):
        self.assertEqual(self.client.get(self.url, secure=True).status_code, 302)
        permission = Permission.objects.get(
            content_type__app_label="enterprise_portal",
            codename="view_chatgptactionreport",
        )
        office = Permission.objects.get(
            content_type__app_label="enterprise_portal",
            codename="view_businessunit",
        )
        self.staff.user_permissions.add(permission, office)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url, secure=True).status_code, 403)
        self.assertNotContains(self.client.get("/company/office/", secure=True), "گزارش‌های متنی اقدامات ChatGPT")
        self.client.force_login(self.root)
        self.assertEqual(self.client.get(self.url, secure=True).status_code, 200)

    def test_empty_page_does_not_claim_work_was_done(self):
        self.client.force_login(self.root)
        response = self.client.get(self.url, secure=True)
        self.assertContains(response, "هنوز گزارش اقدامی")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("noindex", response["X-Robots-Tag"])

    def test_numbered_receipt_text_filters_and_escaped_markup(self):
        self.receipt(body="<script>alert(1)</script>\nتغییر کد ثبت شد")
        self.client.force_login(self.root)
        response = self.client.get(self.url + "?cycle=05&outcome=partial", secure=True)
        self.assertContains(response, "05-0004")
        self.assertContains(response, "github-actions-41338335989")
        self.assertNotContains(response, "<script>alert(1)</script>", html=False)
        self.assertContains(response, "&lt;script&gt;", html=False)
        self.assertEqual(self.client.get(self.url + "?outcome=nonsense", secure=True).status_code, 400)
        self.assertEqual(self.client.get(self.url + "?cycle=" + "x"*30, secure=True).status_code, 400)
        self.assertNotContains(self.client.get(self.url + "?cycle=06", secure=True), "05-0004")

    def test_no_unproved_or_unsafe_completed_receipts(self):
        with self.assertRaises(ValidationError):
            self.receipt(evidence_url="http://example.com/fake", outcome="completed")
        with self.assertRaises(ValidationError):
            self.receipt(evidence_url="https://github.com.evil.com/mojtabarozegar11-ship-it/Saeit/pull/1774")
        with self.assertRaises(ValidationError):
            self.receipt(evidence_reviewed=True)
        self.assertEqual(ChatGPTActionReport.objects.count(), 0)

    def test_receipts_are_immutable_and_unique(self):
        item = self.receipt()
        with self.assertRaises(ValidationError):
            self.receipt()
        item.body = "تحریف محتوا"
        with self.assertRaises(ValidationError):
            item.save()
        with self.assertRaises(ValidationError):
            item.delete()
        self.assertEqual(ChatGPTActionReport.objects.count(), 1)

    def test_report_route_is_read_only(self):
        self.client.force_login(self.root)
        self.assertEqual(self.client.post(self.url, {}, secure=True).status_code, 405)
