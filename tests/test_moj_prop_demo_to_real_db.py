"""Isolated Django persistence tests for simulated Plan 1 stages, synthetic only."""
from datetime import datetime, timezone
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from prop_firm.models import PropAccount, PropTrader, PropChallengeEnrollment


class ActualDemoPhaseModelTests(TestCase):
    """Isolated synthetic DB only: prove demo phases don't need broker KYC."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="plan1_demo_no_live_account_ci", password="only-in-tests"
        )
        cls.trader = PropTrader.objects.create(
            user=cls.user, kyc_status="not_started",
            eligibility_status="not_reviewed",
        )
        # Synthetic settled fixture, NOT an independently verified real sale.
        cls.enrollment = PropChallengeEnrollment.objects.create(
            trader=cls.trader,
            verified_invoice_ref="CI-DEMO-BOUNDARY-SYNTHETIC",
            plan_code="MOJ-PROP-01",
            settlement_verified=True,
            confirmed_at=datetime(2026, 11, 16, tzinfo=timezone.utc),
        )

    def test_simulated_phase_one_can_be_recorded_without_broker_kyc(self):
        account = PropAccount.objects.create(
            trader=self.trader, kind=PropAccount.Kind.PHASE_ONE,
            challenge_enrollment=self.enrollment,
            starting_capital_usd=Decimal("100.00"),
        )
        self.assertEqual(account.kind, "phase_one")
        self.assertEqual(self.trader.kyc_status, "not_started")

    def test_simulated_phase_two_can_be_recorded_without_broker_kyc(self):
        account = PropAccount.objects.create(
            trader=self.trader, kind=PropAccount.Kind.PHASE_TWO,
            challenge_enrollment=self.enrollment,
            starting_capital_usd=Decimal("100.00"),
        )
        self.assertEqual(account.kind, "phase_two")
        self.assertEqual(self.trader.kyc_status, "not_started")

    def test_unverified_demo_trader_cannot_be_funded_via_model(self):
        with self.assertRaises(ValidationError):
            PropAccount.objects.create(
                trader=self.trader, kind=PropAccount.Kind.FUNDED,
                challenge_enrollment=self.enrollment,
                starting_capital_usd=Decimal("100.00"),
                reference="CI-ONLY-NOT-REAL-BROKER",
            )
        self.assertEqual(PropAccount.objects.filter(
            kind=PropAccount.Kind.FUNDED).count(), 0)

    def test_demo_accounts_do_not_automatically_open_real_broker_account(self):
        PropAccount.objects.create(
            trader=self.trader, kind=PropAccount.Kind.PHASE_ONE,
            challenge_enrollment=self.enrollment,
        )
        PropAccount.objects.create(
            trader=self.trader, kind=PropAccount.Kind.PHASE_TWO,
            challenge_enrollment=self.enrollment,
        )
        self.assertEqual(
            PropAccount.objects.filter(kind=PropAccount.Kind.FUNDED).count(), 0)
