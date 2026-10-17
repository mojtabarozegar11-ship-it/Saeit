"""Financial management reporting: separate units and currencies, no ledger writes."""
from datetime import date
from decimal import Decimal
import csv
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.utils import timezone

from enterprise_portal.models import (
    BusinessUnit, JournalEntry, JournalLine, LedgerAccount,
)
from enterprise_portal.services import post_journal
from .models import UnitMembership
from .financial_reporting import calculate_management_income

D = Decimal
STORE = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=STORE, DEBUG=False, ALLOWED_HOSTS=["testserver"])
class ManagementIncomeTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="owner-income", email="income@example.org", password="test-not-production",
        )
        self.accountant = get_user_model().objects.create_user(
            username="farm-accountant", password="test-not-production", is_staff=True,
        )
        self.untrusted = get_user_model().objects.create_user(
            username="unauthorized-accountant", password="test-not-production", is_staff=True,
        )
        self.farm = BusinessUnit.objects.create(code="farm", name="کشاورزی")
        self.factory = BusinessUnit.objects.create(code="factory", name="کارخانه")
        UnitMembership.objects.create(user=self.accountant, unit=self.farm, role="finance", active=True)
        allowed = Permission.objects.filter(
            content_type__app_label__in=("enterprise_portal", "ecosystem_hub"),
            codename__in=("view_businessunit", "view_organization", "view_journalentry", "view_ledgeraccount"),
        )
        self.accountant.user_permissions.add(*list(allowed))
        self.accounts = {}
        for unit in (self.farm, self.factory):
            self.accounts[unit.code] = {
                "cash": LedgerAccount.objects.create(unit=unit, code="101", name="نقد", category="asset"),
                "income": LedgerAccount.objects.create(unit=unit, code="401", name="درآمد", category="income"),
                "expense": LedgerAccount.objects.create(unit=unit, code="501", name="هزینه", category="expense"),
            }
        self.count = 0

    def journal(self, unit, currency, *, expense=False, amount="100", posted=True, booked_on=date(2026, 10, 15)):
        self.count += 1
        item = JournalEntry.objects.create(
            unit=unit, reference=f"JV-{self.count}", booked_on=booked_on,
            currency=currency, description="سند دوره‌ای", created_by=self.owner,
        )
        accounts = self.accounts[unit.code]
        if expense:
            JournalLine.objects.create(entry=item, account=accounts["expense"], debit=D(amount), credit=D("0"))
            JournalLine.objects.create(entry=item, account=accounts["cash"], debit=D("0"), credit=D(amount))
        else:
            JournalLine.objects.create(entry=item, account=accounts["cash"], debit=D(amount), credit=D("0"))
            JournalLine.objects.create(entry=item, account=accounts["income"], debit=D("0"), credit=D(amount))
        if posted:
            post_journal(item.pk, self.owner)
        return item

    def url(self, ext=""):
        return "/company/office/ecosystem/finance/income/" + ext

    def test_period_income_expense_and_result_are_actual_posted_ledger_categories(self):
        self.journal(self.farm, "IRR", amount="250")
        self.journal(self.farm, "IRR", expense=True, amount="90")
        self.journal(self.farm, "USD", amount="80")
        self.journal(self.factory, "IRR", amount="900")
        self.journal(self.farm, "IRR", amount="10000", posted=False)
        self.client.force_login(self.owner)
        response = self.client.get(self.url()+"?start=2026-10-01&end=2026-10-31", secure=True)
        self.assertEqual(response.status_code, 200)
        entries = {(r["unit_code"], r["currency"]): r for r in response.context["totals"]}
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[("farm", "IRR")]["income"], D("250"))
        self.assertEqual(entries[("farm", "IRR")]["expense"], D("90"))
        self.assertEqual(entries[("farm", "IRR")]["result"], D("160"))
        self.assertEqual(entries[("farm", "USD")]["result"], D("80"))
        self.assertEqual(entries[("factory", "IRR")]["result"], D("900"))
        self.assertNotContains(response, "10000.00")
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(JournalEntry.objects.count(), 5)

    def test_posted_entry_outside_date_range_excluded(self):
        self.journal(self.farm, "IRR", amount="330", booked_on=date(2026, 9, 30))
        self.client.force_login(self.owner)
        result = self.client.get(self.url()+"?start=2026-10-01&end=2026-10-31", secure=True)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.context["totals"])

    def test_unit_and_currency_filter_do_not_combine_accounts(self):
        self.journal(self.farm, "IRR", amount="250")
        self.journal(self.farm, "USD", amount="60")
        self.journal(self.factory, "IRR", amount="900")
        self.client.force_login(self.accountant)
        response = self.client.get(self.url()+"?unit=farm&currency=USD&start=2026-01-01&end=2026-12-31", secure=True)
        self.assertEqual(response.status_code, 200)
        totals = response.context["totals"]
        self.assertEqual(len(totals), 1)
        self.assertEqual(totals[0]["currency"], "USD")
        self.assertEqual(totals[0]["result"], D("60"))
        self.assertEqual(totals[0]["unit_code"], "farm")

    def test_unauthorized_unit_query_and_csv_are_not_exposed(self):
        self.journal(self.factory, "IRR", amount="900")
        self.client.force_login(self.accountant)
        for url in (self.url()+"?unit=factory", self.url("income.csv")+"?unit=factory"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url, secure=True).status_code, 404)
        result = self.client.get(self.url(), secure=True)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.context["details"], [])

    def test_unprivileged_and_anonymous_users_cannot_see_private_finances(self):
        self.assertEqual(self.client.get(self.url(), secure=True).status_code, 302)
        self.client.force_login(self.untrusted)
        self.assertEqual(self.client.get(self.url(), secure=True).status_code, 403)
        self.assertEqual(self.client.get(self.url("income.csv"), secure=True).status_code, 403)
        # A staff member with partial finance permissions cannot see account-level results.
        user = self.accountant
        perm = Permission.objects.get(
            content_type__app_label="enterprise_portal", codename="view_ledgeraccount",
        )
        user.user_permissions.remove(perm)
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url(), secure=True).status_code, 403)

    def test_invalid_dates_currency_query_keys_and_duplicates_are_rejected(self):
        self.client.force_login(self.owner)
        for params in (
            "?currency=BTC", "?start=tomorrow", "?start=2026-10-31&end=2026-10-01",
            "?start=1800-01-01", "?start=2026-01-01&start=2026-02-01",
            "?secret=1", "?end=2101-01-01",
        ):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(self.url()+params, secure=True).status_code, 400)

    def test_csv_prevents_formula_execution_in_user_controlled_titles(self):
        self.accounts["farm"]["income"].name = '=HYPERLINK("https://invalid.example","click")'
        self.accounts["farm"]["income"].save()
        self.journal(self.farm, "IRR", amount="130")
        self.client.force_login(self.accountant)
        result = self.client.get(self.url("income.csv")+"?start=2026-10-01&end=2026-10-31", secure=True)
        self.assertEqual(result.status_code, 200)
        self.assertIn("attachment", result["Content-Disposition"])
        self.assertIn("no-store", result["Cache-Control"])
        rows = list(csv.reader(StringIO(result.content.decode("utf-8-sig"))))
        self.assertTrue(any(v.startswith("'=HYPERLINK") for row in rows for v in row))
        self.assertEqual(JournalEntry.objects.count(), 1)

    def test_corrections_can_be_negative_and_no_false_zeroing(self):
        self.journal(self.farm, "IRR", amount="150")
        # Correcting entry reverses income, and debit balances are not dropped.
        item = JournalEntry.objects.create(
            unit=self.farm, reference="REV-1", booked_on=date(2026, 10, 15),
            currency="IRR", description="اصلاح درآمد", created_by=self.owner,
        )
        accounts = self.accounts["farm"]
        JournalLine.objects.create(entry=item, account=accounts["income"], debit=D("40"), credit=D("0"))
        JournalLine.objects.create(entry=item, account=accounts["cash"], debit=D("0"), credit=D("40"))
        post_journal(item.pk, self.owner)
        details, totals = calculate_management_income(
            allowed_units=BusinessUnit.objects.filter(pk=self.farm.pk),
            start=date(2026, 10, 1), end=date(2026, 10, 31),
        )
        self.assertEqual(totals[0]["income"], D("110"))
        self.assertEqual(totals[0]["result"], D("110"))
        self.assertEqual(len(details), 1)
