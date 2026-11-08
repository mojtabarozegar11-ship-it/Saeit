from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.contrib import admin
from django.core.exceptions import ValidationError
from .admin import JournalEntryAdmin
from .models import Account, JournalEntry, JournalLine
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

    def test_unbalanced_posted_entry_is_reported_not_crashed(self):
        JournalEntry.objects.create(reference="JV-BAD", occurred_on=date(2026, 11, 4), memo="نامتوازن", status=JournalEntry.Status.POSTED)
        self.assertFalse(ledger_summary()["integrity"]["balanced_posted_entries"])

    def test_journal_requires_at_least_two_lines(self):
        one = JournalEntry.objects.create(
            reference="JV-ONE", occurred_on=date(2026, 11, 8),
            memo="one-sided test", status=JournalEntry.Status.DRAFT
        )
        JournalLine.objects.create(
            entry=one, account=self.cash, debit=Decimal("10.00")
        )
        with self.assertRaises(ValidationError):
            one.validate_balanced()

    def test_zero_posted_entries_is_not_treated_as_verified_balanced(self):
        JournalLine.objects.all().delete()
        JournalEntry.objects.all().delete()
        summary = ledger_summary()
        self.assertEqual(summary["integrity"]["evidence_count"], 0)
        self.assertTrue(summary["integrity"]["no_posted_entries"])
        self.assertFalse(summary["integrity"]["balanced_posted_entries"])

    def test_posted_journal_not_mutable_through_admin(self):
        editor = get_user_model().objects.create_superuser(
            username="finance-qa", email="qa@example.test", password="local-test-only"
        )
        request = RequestFactory().get("/admin/accounting/journalentry/")
        request.user = editor
        posted = JournalEntry.objects.get(reference="JV-1")
        entry_admin = JournalEntryAdmin(JournalEntry, admin.site)
        self.assertFalse(entry_admin.has_change_permission(request, posted))
        self.assertFalse(entry_admin.has_delete_permission(request, posted))
