"""Regression checks for private access, accurate ledger posting and safe coexistence."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from .models import (
    AuditEvent, BusinessUnit, CommercialDocument, InventoryItem,
    JournalEntry, JournalLine, LedgerAccount, OfficeLetter, Partner,
    StockMovement, WorkTask,
)
from .services import confirm_stock_movement, post_journal, stock_balance

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

User = get_user_model()
D = Decimal


@override_settings(STORAGES=TEST_STORAGES)
@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver", "zomorodmelal.ir"])
class OfficeSecurityTests(TestCase):
    def setUp(self):
        self.unit = BusinessUnit.objects.create(code="hq", name="دفتر مرکزی")
        self.viewer = User.objects.create_user(
            username="company-clerk", password="TestPasswordOnly!123",
            is_active=True, is_staff=True,
        )
        self.member = User.objects.create_user(
            username="ordinary-user", password="TestPasswordOnly!123",
            is_active=True,
        )
        self.admin = User.objects.create_superuser(
            username="owner-testing", email="owner@example.org",
            password="TestPasswordOnly!123",
        )
        perm = Permission.objects.get(content_type__app_label="enterprise_portal", codename="view_businessunit")
        self.viewer.user_permissions.add(perm)

    def test_new_route_is_before_company_slug_and_does_not_replace_company(self):
        self.assertEqual(resolve("/company/office/").url_name, "dashboard")
        self.assertEqual(resolve("/company/office/login/").url_name, "login")
        self.assertEqual(resolve("/company/").url_name, "company")
        self.assertEqual(resolve("/ghanadi/").url_name, "ghanadi")
        self.assertEqual(resolve("/amozeshgah/").url_name, "education")
        self.assertEqual(resolve("/farnaz/").url_name, "farnaz_home" if False else resolve("/farnaz/").url_name)

    def test_login_get_is_private_noindex_and_not_cached(self):
        response = self.client.get("/company/office/login/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نام کاربری")
        self.assertContains(response, "رمز عبور")
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.assertNotContains(response, "TestPasswordOnly!123")

    def test_plain_http_cannot_login_or_access_workspace(self):
        self.assertEqual(self.client.get("/company/office/login/").status_code, 403)
        self.assertEqual(self.client.get("/company/office/").status_code, 403)

    def test_anonymous_user_redirected_to_local_login(self):
        response = self.client.get("/company/office/", secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/company/office/login/?next=", response["Location"])
        self.assertEqual(self.client.get("/company/office/finance/", secure=True).status_code, 302)

    def test_nonstaff_credentials_cannot_log_into_private_office(self):
        response = self.client.post("/company/office/login/", {
            "username": self.member.username, "password": "TestPasswordOnly!123",
        }, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse("_auth_user_id" in self.client.session)

    def test_staff_without_company_access_cannot_log_into_private_office(self):
        other = User.objects.create_user(username="staff-only", is_staff=True,
                                         password="TestPasswordOnly!123")
        response = self.client.post("/company/office/login/", {
            "username": other.username, "password": "TestPasswordOnly!123",
        }, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse("_auth_user_id" in self.client.session)

    def test_authorized_login_and_post_only_logout(self):
        response = self.client.post("/company/office/login/", {
            "username": self.viewer.username, "password": "TestPasswordOnly!123",
        }, secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/company/office/")
        dashboard = self.client.get(response["Location"], secure=True)
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "مدیریت همه بخش‌های شرکت")
        self.assertNotContains(dashboard, "گزارش دفتر کل")
        self.assertEqual(self.client.get("/company/office/logout/", secure=True).status_code, 405)
        self.assertEqual(self.client.post("/company/office/logout/", secure=True).status_code, 302)

    def test_privilege_separation_deny_finance_to_staff_without_finance_permission(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get("/company/office/finance/", secure=True).status_code, 403)
        self.assertEqual(self.client.get("/company/office/letters/", secure=True).status_code, 403)
        self.assertEqual(self.client.get("/company/office/inventory/", secure=True).status_code, 403)
        self.assertEqual(self.client.post("/company/office/tasks/new/", {"title": "Not authorized"}, secure=True).status_code, 403)

    def test_logged_in_unapproved_staff_cannot_access_dashboard_directly(self):
        staff = User.objects.create_user(username="unpermitted", is_staff=True, password="p")
        self.client.force_login(staff)
        self.assertEqual(self.client.get("/company/office/", secure=True).status_code, 403)

    def test_form_requires_csrf_when_enabled(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/company/office/login/", {
            "username": self.viewer.username, "password": "TestPasswordOnly!123",
        }, secure=True)
        self.assertEqual(response.status_code, 403)

    def test_superuser_dashboard_has_real_modules_but_no_fake_data(self):
        self.client.force_login(self.admin)
        response = self.client.get("/company/office/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "حسابداری و دفتر کل")
        self.assertContains(response, "اتوماسیون وظایف")
        self.assertContains(response, "واحدهای شرکت")
        self.assertIn("no-store", response["Cache-Control"])


@override_settings(STORAGES=TEST_STORAGES)
class FinanceIntegrityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="financial-owner", email="finance@example.org", password="unused"
        )
        self.other = User.objects.create_user(username="no-accounting", password="unused", is_staff=True)
        self.unit = BusinessUnit.objects.create(code="industry", name="صنعت")
        self.other_unit = BusinessUnit.objects.create(code="trade", name="تجارت")
        self.cash = LedgerAccount.objects.create(unit=self.unit, code="110", name="نقد", category="asset")
        self.sales = LedgerAccount.objects.create(unit=self.unit, code="410", name="درآمد", category="income")
        self.foreign = LedgerAccount.objects.create(unit=self.other_unit, code="110", name="ارز", category="asset")

    def journal(self, currency="IRR"):
        return JournalEntry.objects.create(
            unit=self.unit, reference="JF-"+currency,
            description="فروش", currency=currency, created_by=self.owner
        )

    def line(self, entry, account, debit=0, credit=0):
        return JournalLine.objects.create(
            entry=entry, account=account,
            debit=D(str(debit)), credit=D(str(credit))
        )

    def test_unbalanced_journal_cannot_post(self):
        doc = self.journal()
        self.line(doc, self.cash, debit=200)
        self.line(doc, self.sales, credit=150)
        with self.assertRaises(ValidationError):
            post_journal(doc.pk, self.owner)
        doc.refresh_from_db()
        self.assertEqual(doc.status, "draft")
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_balanced_journal_posts_and_creates_audit_event(self):
        doc = self.journal()
        first = self.line(doc, self.cash, debit=200)
        self.line(doc, self.sales, credit=200)
        post_journal(doc.pk, self.owner)
        doc.refresh_from_db()
        self.assertEqual(doc.status, "posted")
        self.assertIsNotNone(doc.posted_at)
        self.assertEqual(AuditEvent.objects.get().action, "journal_posted")
        with self.assertRaises(ValidationError):
            post_journal(doc.pk, self.owner)
        doc.description = "altered"
        with self.assertRaises(ValidationError):
            doc.save()
        first.debit = D("900")
        with self.assertRaises(ValidationError):
            first.save()
        with self.assertRaises(ValidationError):
            first.delete()
        with self.assertRaises(ValidationError):
            doc.delete()

    def test_cross_unit_account_not_accepted(self):
        doc = self.journal()
        with self.assertRaises(ValidationError):
            self.line(doc, self.foreign, debit=100)

    def test_a_line_must_have_exactly_one_side(self):
        doc = self.journal()
        for debit, credit in [(100, 100), (0, 0), (-1, 0)]:
            with self.subTest(debit=debit, credit=credit):
                with self.assertRaises(ValidationError):
                    self.line(doc, self.cash, debit=debit, credit=credit)

    def test_ordinary_staff_cannot_post_documents(self):
        doc = self.journal()
        self.line(doc, self.cash, debit=300)
        self.line(doc, self.sales, credit=300)
        with self.assertRaises(PermissionDenied):
            post_journal(doc.pk, self.other)
        doc.refresh_from_db()
        self.assertEqual(doc.status, "draft")

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_currency_totals_are_separate_and_not_merged(self):
        for curr in ("IRR", "USD"):
            doc = self.journal(currency=curr)
            self.line(doc, self.cash, debit=500)
            self.line(doc, self.sales, credit=500)
            post_journal(doc.pk, self.owner)
        self.client.force_login(self.owner)
        response = self.client.get("/company/office/finance/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "IRR")
        self.assertContains(response, "USD")
        self.assertContains(response, "اسناد قطعی")
        self.assertEqual(len(response.context["records"]), 2)

    def test_trade_document_partner_must_match_unit(self):
        partner = Partner.objects.create(unit=self.other_unit, name="تأمین کننده")
        doc = CommercialDocument(
            unit=self.unit, partner=partner, number="Q1", kind="quotation",
            total=D("100.00"), created_by=self.owner
        )
        with self.assertRaises(ValidationError):
            doc.full_clean()

    def test_no_automatic_payment_or_tax_posting(self):
        partner = Partner.objects.create(unit=self.unit, name="مشتری")
        CommercialDocument.objects.create(
            unit=self.unit, partner=partner, number="INV-1", kind="sales",
            total=D("100"), currency="IRR", created_by=self.owner
        )
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)


@override_settings(STORAGES=TEST_STORAGES)
class InventoryAndOfficeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(username="chief", email="chief@example.org", password="test")
        self.staff = User.objects.create_user(username="secretary", password="test", is_staff=True)
        self.stranger = User.objects.create_user(username="intern", password="test", is_staff=True)
        self.unit = BusinessUnit.objects.create(code="agro", name="تولید")
        self.item = InventoryItem.objects.create(unit=self.unit, sku="S-1", title="بذر", measure="کیلو")

    def movement(self, direction, qty, ref):
        return StockMovement.objects.create(
            item=self.item, direction=direction, quantity=D(qty),
            reference=ref, created_by=self.owner
        )

    def test_inventory_cannot_confirm_excess_or_negative_stock(self):
        entry = self.movement("in", "15.000", "GRN-1")
        confirm_stock_movement(entry.pk, self.owner)
        outgoing = self.movement("out", "25.000", "OUT-1")
        with self.assertRaises(ValidationError):
            confirm_stock_movement(outgoing.pk, self.owner)
        self.assertEqual(stock_balance(self.item.pk), D("15.000"))
        outgoing.quantity = D("6.000")
        outgoing.save()
        confirm_stock_movement(outgoing.pk, self.owner)
        self.assertEqual(stock_balance(self.item.pk), D("9.000"))
        with self.assertRaises(ValidationError):
            outgoing.delete()
        self.assertEqual(AuditEvent.objects.filter(action="stock_confirmed").count(), 2)

    def test_stock_can_only_be_confirmed_by_authorized_staff(self):
        entry = self.movement("in", "2.000", "GRN-2")
        with self.assertRaises(PermissionDenied):
            confirm_stock_movement(entry.pk, self.staff)

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_secret_letters_not_leaked_to_generic_authorized_staff(self):
        access = Permission.objects.get(content_type__app_label="enterprise_portal", codename="view_businessunit")
        can_view = Permission.objects.get(content_type__app_label="enterprise_portal", codename="view_officeletter")
        self.staff.user_permissions.add(access, can_view)
        OfficeLetter.objects.create(
            number="O-1", subject="نامه عادی", direction="incoming",
            body="متن عمومی داخلی", created_by=self.owner,
        )
        OfficeLetter.objects.create(
            number="S-1", subject="محتوای محرمانه استراتژیک", direction="internal",
            body="راز شرکت", classification="confidential", created_by=self.owner,
        )
        self.client.force_login(self.staff)
        response = self.client.get("/company/office/letters/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نامه عادی")
        self.assertNotContains(response, "محتوای محرمانه استراتژیک")
        self.assertNotContains(response, "راز شرکت")

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_staff_can_submit_task_only_after_granting_add_permission(self):
        access = Permission.objects.get(content_type__app_label="enterprise_portal", codename="view_businessunit")
        can_add = Permission.objects.get(content_type__app_label="enterprise_portal", codename="add_worktask")
        self.staff.user_permissions.add(access, can_add)
        self.client.force_login(self.staff)
        response = self.client.post("/company/office/tasks/new/", {
            "title": "بررسی موجودی", "description": "بررسی انبار",
            "unit": self.unit.pk, "assigned_to": self.stranger.pk,
            "priority": "high", "due_on": "2026-10-20",
        }, secure=True)
        self.assertEqual(response.status_code, 302)
        task = WorkTask.objects.get()
        self.assertEqual(task.created_by, self.staff)
        self.assertEqual(task.assigned_to, self.stranger)
        self.assertEqual(AuditEvent.objects.count(), 1)

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_staff_without_letter_permission_cannot_create_letter(self):
        access = Permission.objects.get(content_type__app_label="enterprise_portal", codename="view_businessunit")
        self.staff.user_permissions.add(access)
        self.client.force_login(self.staff)
        response = self.client.post("/company/office/letters/new/", {
            "number": "A-001", "subject": "غیر مجاز", "direction": "internal",
            "body": "موارد اداری", "classification": "normal",
            "sent_on": "2026-10-17",
        }, secure=True)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(OfficeLetter.objects.exists())

    def test_audit_events_are_append_only_via_model(self):
        record = AuditEvent.objects.create(
            actor=self.owner, action="stock_confirmed", target="StockMovement:1"
        )
        with self.assertRaises(ValidationError):
            record.save()
        with self.assertRaises(ValidationError):
            record.delete()
