from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import Account, JournalEntry, JournalLine


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
