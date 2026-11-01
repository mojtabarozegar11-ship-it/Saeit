"""Posted management reports must reject inconsistent account/unit relationships."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from enterprise_portal.models import BusinessUnit, JournalEntry, JournalLine, LedgerAccount
from .financial_reporting import calculate_management_income


class FinancialUnitIntegrityTests(TestCase):
    def test_mismatched_posted_account_blocks_incomplete_totals(self):
        user = get_user_model().objects.create_user(username="integrity-user")
        farm = BusinessUnit.objects.create(code="farm-integrity", name="Farm")
        other = BusinessUnit.objects.create(code="other-integrity", name="Other")
        foreign_account = LedgerAccount.objects.create(
            unit=other, code="401", name="Other unit revenue", category="income",
        )
        entry = JournalEntry.objects.create(
            unit=farm, reference="INTEGRITY-1", booked_on=date(2026, 10, 15),
            currency="IRR", description="Imported historical row", created_by=user,
        )
        JournalEntry.objects.filter(pk=entry.pk).update(status="posted")
        JournalLine.objects.bulk_create([
            JournalLine(entry=entry, account=foreign_account,
                        debit=Decimal("0"), credit=Decimal("75")),
        ])
        with self.assertRaisesMessage(
            Exception, "Posted journal contains cross-unit account rows."
        ):
            calculate_management_income(
                allowed_units=BusinessUnit.objects.filter(pk=farm.pk),
                start=date(2026, 10, 1), end=date(2026, 10, 31),
            )

    def test_other_unit_is_not_visible_or_blocking(self):
        user = get_user_model().objects.create_user(username="integrity-user2")
        farm = BusinessUnit.objects.create(code="farm-only", name="Farm")
        other = BusinessUnit.objects.create(code="other-only", name="Other")
        foreign_account = LedgerAccount.objects.create(
            unit=farm, code="401", name="Farm revenue", category="income",
        )
        entry = JournalEntry.objects.create(
            unit=other, reference="INTEGRITY-2", booked_on=date(2026, 10, 15),
            currency="IRR", description="Other unit import", created_by=user,
        )
        JournalEntry.objects.filter(pk=entry.pk).update(status="posted")
        JournalLine.objects.bulk_create([
            JournalLine(entry=entry, account=foreign_account,
                        debit=Decimal("0"), credit=Decimal("75")),
        ])
        details, totals = calculate_management_income(
            allowed_units=BusinessUnit.objects.filter(pk=farm.pk),
            start=date(2026, 10, 1), end=date(2026, 10, 31),
        )
        self.assertEqual(details, [])
        self.assertEqual(totals, [])
