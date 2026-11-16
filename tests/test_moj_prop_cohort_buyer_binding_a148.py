"""A148 — prevent an unrelated phase from donating a 50th closed trade.

Django isolated-db synthetic broker data only. The fixture's paid flag is a
test value, not proof of a TRON settlement or legally eligible real customer.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from prop_firm.models import (
    PropAccount, PropChallengeEnrollment, PropExecution, PropTrader,
)
from prop_firm.portal import account_projection
from prop_firm.rules import POLICY


class PaidCohortTradeIdentityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        primary = get_user_model().objects.create_user(
            username="a148_buyer_fixture", password="ci-only-never-live"
        )
        outsider = get_user_model().objects.create_user(
            username="a148_other_fixture", password="ci-only-never-live"
        )
        cls.buyer = PropTrader.objects.create(user=primary)
        cls.other_buyer = PropTrader.objects.create(user=outsider)
        cls.purchase = PropChallengeEnrollment.objects.create(
            trader=cls.buyer,
            plan_code="MOJ-PROP-01",
            verified_invoice_ref="a148-no-real-transaction-fixture",
            confirmed_at=timezone.now() - timedelta(days=3),
            settlement_verified=True,
            terms_version=POLICY.version,
        )
        cls.first = PropAccount.objects.create(
            trader=cls.buyer, kind=PropAccount.Kind.PHASE_ONE,
            challenge_enrollment=cls.purchase,
            tier_index=0, starting_capital_usd=Decimal("100.00"),
            policy_version=POLICY.version,
        )
        cls.second = PropAccount.objects.create(
            trader=cls.buyer, kind=PropAccount.Kind.PHASE_TWO,
            challenge_enrollment=cls.purchase,
            tier_index=0, starting_capital_usd=Decimal("100.00"),
            policy_version=POLICY.version,
        )
        cls.donor = PropAccount.objects.create(
            trader=cls.buyer, kind=PropAccount.Kind.PHASE_ONE,
            challenge_enrollment=cls.purchase,
            tier_index=0, starting_capital_usd=Decimal("100.00"),
            policy_version=POLICY.version,
        )
        cls.close_at = cls.purchase.confirmed_at + timedelta(days=1)
        PropExecution.objects.bulk_create([
            PropExecution(
                account=cls.first, external_event_id=f"a148-valid-{i}",
                external_position_id=f"a148-position-{i}",
                data_source="fixture-simulator", execution_origin="manual",
                symbol="XAUUSD", closed_at=cls.close_at,
                gross_realized_usd=Decimal("1.00"),
                total_fees_usd=Decimal("0.00"),
                reconciliation_status="verified",
            ) for i in range(49)
        ])
        cls.donor_event = PropExecution.objects.create(
            account=cls.donor, external_event_id="a148-donor-event",
            external_position_id="a148-position-49",
            data_source="fixture-simulator", execution_origin="bot",
            symbol="XAUUSD", closed_at=cls.close_at,
            gross_realized_usd=Decimal("1.00"),
            total_fees_usd=Decimal("0.00"),
            reconciliation_status="verified",
        )

    def count(self):
        phase = PropAccount.objects.get(pk=self.second.pk)
        result = account_projection(phase)
        self.assertTrue(result["purchase_window_valid"])
        self.assertIsNotNone(result["challenge_trade_count"])
        return result["challenge_trade_count"]

    def assert_only_fortynine(self):
        result = self.count()
        self.assertEqual(result.valid_closed_positions, 49)
        self.assertFalse(result.sufficient)

    def test_01_valid_matching_phase_can_supply_fiftieth(self):
        result = self.count()
        self.assertEqual(result.valid_closed_positions, 50)
        self.assertTrue(result.sufficient)

    def test_02_foreign_trader_account_cannot_donate_fiftieth(self):
        PropAccount.objects.filter(pk=self.donor.pk).update(trader=self.other_buyer)
        self.assert_only_fortynine()

    def test_03_legacy_policy_account_cannot_donate_fiftieth(self):
        PropAccount.objects.filter(pk=self.donor.pk).update(
            policy_version="2026-11-14/v1.1"
        )
        self.assert_only_fortynine()

    def test_04_different_capital_tier_cannot_donate_fiftieth(self):
        PropAccount.objects.filter(pk=self.donor.pk).update(tier_index=1)
        self.assert_only_fortynine()

    def test_05_different_starting_balance_cannot_donate_fiftieth(self):
        PropAccount.objects.filter(pk=self.donor.pk).update(
            starting_capital_usd=Decimal("200.00")
        )
        self.assert_only_fortynine()

    def test_06_different_purchase_account_cannot_donate_fiftieth(self):
        alternative = PropChallengeEnrollment.objects.create(
            trader=self.buyer, plan_code="MOJ-PROP-01",
            verified_invoice_ref="a148-other-fictional-receipt",
            confirmed_at=self.purchase.confirmed_at,
            settlement_verified=True,
            terms_version=POLICY.version,
        )
        PropAccount.objects.filter(pk=self.donor.pk).update(
            challenge_enrollment=alternative
        )
        self.assert_only_fortynine()

    def test_07_funded_account_cannot_donate_challenge_trade(self):
        PropAccount.objects.filter(pk=self.donor.pk).update(kind=PropAccount.Kind.FUNDED)
        self.assert_only_fortynine()

    def test_08_unverified_donor_trade_never_counts(self):
        PropExecution.objects.filter(pk=self.donor_event.pk).update(
            reconciliation_status="pending"
        )
        self.assert_only_fortynine()

    def test_09_donor_close_after_paid_window_never_counts(self):
        PropExecution.objects.filter(pk=self.donor_event.pk).update(
            closed_at=self.purchase.confirmed_at + timedelta(days=28)
        )
        self.assert_only_fortynine()

    def test_10_duplicate_position_from_second_phase_not_double_counted(self):
        PropExecution.objects.filter(pk=self.donor_event.pk).update(
            external_position_id="a148-position-1"
        )
        self.assert_only_fortynine()

    def test_11_outsider_account_cannot_be_repaired_by_stale_relation_cache(self):
        # Read a stale related object first, then mutate the backing DB row.
        unused_cached = self.second.challenge_enrollment
        self.assertEqual(unused_cached.pk, self.purchase.pk)
        PropAccount.objects.filter(pk=self.donor.pk).update(trader=self.other_buyer)
        self.assert_only_fortynine()

    def test_12_matching_after_single_invalid_metadata_repaired_in_fixture(self):
        PropAccount.objects.filter(pk=self.donor.pk).update(
            tier_index=1, policy_version="2026-11-14/v1.1"
        )
        self.assert_only_fortynine()
        PropAccount.objects.filter(pk=self.donor.pk).update(
            tier_index=0, policy_version=POLICY.version
        )
        result = self.count()
        self.assertEqual(result.valid_closed_positions, 50)
        self.assertTrue(result.sufficient)
