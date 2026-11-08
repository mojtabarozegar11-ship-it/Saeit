from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from .models import Account, JournalEntry, JournalLine
from .admin import JournalEntryAdmin, AccountAdmin
from .services import ledger_summary


class AccountingDashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="accountant", password="safe-pass-123", is_staff=True)
        self.cash = Account.objects.create(code="1100", name="بانک", kind=Account.Kind.ASSET)
        self.revenue = Account.objects.create(code="4100", name="درآمد فروش", kind=Account.Kind.REVENUE)
        entry = JournalEntry.objects.create(reference="JV-1", occurred_on=date(2026, 11, 4), memo="فروش نمونه", status=JournalEntry.Status.POSTED)
        JournalLine.objects.create(entry=entry, account=self.cash, debit=Decimal("100.00"))
        JournalLine.objects.create(entry=entry, account=self.revenue, credit=Decimal("100.00"))

    def test_requires_staff(self):
        response = self.client.get("/staff/command-center/accounting/")
        self.assertEqual(response.status_code, 302)

    def test_summary_is_balanced(self):
        self.client.force_login(self.user)
        response = self.client.get("/staff/command-center/accounting/api/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["integrity"]["balanced_posted_entries"])

    def test_inactive_account_with_posted_activity_remains_visible(self):
        self.cash.is_active = False
        self.cash.save(update_fields=["is_active"])
        self.assertIn("1100", {item["code"] for item in ledger_summary()["accounts"]})

    def test_inactive_unused_account_hidden_and_draft_not_counted(self):
        Account.objects.create(code="1200", name="Unused", kind=Account.Kind.ASSET, is_active=False)
        draft = JournalEntry.objects.create(reference="JV-DRAFT", occurred_on=date(2026, 11, 7),
                                            memo="Unposted", status=JournalEntry.Status.DRAFT)
        JournalLine.objects.create(entry=draft, account=self.cash, debit=Decimal("700.00"))
        row = next(r for r in ledger_summary()["accounts"] if r["code"] == "1100")
        self.assertEqual(row["debit"], "100.00")
        self.assertNotIn("1200", {r["code"] for r in ledger_summary()["accounts"]})
        self.assertEqual(ledger_summary()["draft_entries"], 1)

    def test_accounting_summary_uses_bounded_number_of_queries(self):
        with self.assertNumQueries(4):
            summary = ledger_summary()
        self.assertEqual(summary["posted_entries"], 1)
        self.assertEqual(summary["recent_entries"][0]["total"], "100.00")

    def test_unbalanced_posted_entry_is_reported_not_crashed(self):
        JournalEntry.objects.create(reference="JV-BAD", occurred_on=date(2026, 11, 4), memo="نامتوازن", status=JournalEntry.Status.POSTED)
        self.assertFalse(ledger_summary()["integrity"]["balanced_posted_entries"])

    def test_posted_account_identity_is_readonly_in_admin(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        request = RequestFactory().get("/admin/accounting/account/")
        request.user = self.user
        model_admin = AccountAdmin(Account, admin.site)
        for account in (self.cash, self.revenue):
            form = model_admin.get_form(request, account)
            self.assertNotIn("code", form.base_fields)
            self.assertNotIn("kind", form.base_fields)
            self.assertIn("name", form.base_fields)

    def test_unused_account_identity_remains_editable_in_admin(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        unused = Account.objects.create(code="1200", name="Unused", kind=Account.Kind.ASSET)
        request = RequestFactory().get("/admin/accounting/account/")
        request.user = self.user
        form = AccountAdmin(Account, admin.site).get_form(request, unused)
        self.assertIn("code", form.base_fields)
        self.assertIn("kind", form.base_fields)

    def test_posted_account_identity_is_rejected_on_model_save(self):
        self.cash.kind = Account.Kind.EXPENSE
        with self.assertRaises(ValidationError):
            self.cash.save(update_fields=["kind"])
        self.cash.refresh_from_db()
        self.assertEqual(self.cash.kind, Account.Kind.ASSET)
        self.cash.code = "1199"
        with self.assertRaises(ValidationError):
            self.cash.save(update_fields=["code"])
        self.cash.refresh_from_db()
        self.assertEqual(self.cash.code, "1100")

    def test_unused_account_identity_can_change_on_model_save(self):
        unused = Account.objects.create(code="1200", name="Unused", kind=Account.Kind.ASSET)
        unused.code = "1201"
        unused.kind = Account.Kind.LIABILITY
        unused.save(update_fields=["code", "kind"])
        unused.refresh_from_db()
        self.assertEqual(unused.code, "1201")
        self.assertEqual(unused.kind, Account.Kind.LIABILITY)

    def test_posted_entry_cannot_be_changed_or_deleted_from_admin(self):
        entry = JournalEntry.objects.get(reference="JV-1")
        request = RequestFactory().get("/admin/accounting/journalentry/")
        request.user = self.user
        model_admin = JournalEntryAdmin(JournalEntry, admin.site)
        self.assertFalse(model_admin.has_change_permission(request, entry))
        self.assertFalse(model_admin.has_delete_permission(request, entry))
        with self.assertRaises(ValidationError):
            model_admin.delete_queryset(request, JournalEntry.objects.filter(pk=entry.pk))
