"""C145: reconciled broker evidence must not impersonate a paid MOJ PROP purchase.

All users, evidence and payment flags below are isolated synthetic Django fixtures.
They do NOT create/verify any actual client invoice, TRON settlement or broker trade.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from prop_firm.models import (
    PropTrader, PropChallengeEnrollment, PropAccount,
    PropExecution, PropEquityObservation,
)
from prop_firm.portal import account_projection


class PaidChallengePresentationGateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user(
            username="c145_synthetic_only", password="CI-only"
        )
        cls.trader = PropTrader.objects.create(user=user)
        cls.base = (timezone.now() - timedelta(days=1)).replace(
            hour=12, minute=0, second=0, microsecond=0
        )
        cls.purchase = PropChallengeEnrollment.objects.create(
            trader=cls.trader,
            verified_invoice_ref="C145-SYNTHETIC-NO-CHAIN-RECEIPT",
            plan_code="MOJ-PROP-01",
            confirmed_at=cls.base-timedelta(days=1),
            settlement_verified=True,  # synthetic fixture only
        )
        cls.account = PropAccount.objects.create(
            trader=cls.trader, challenge_enrollment=cls.purchase,
            kind=PropAccount.Kind.PHASE_ONE,
            status=PropAccount.Status.ACTIVE,
            reconciled_by_operator=True,
            opened_at=cls.base-timedelta(hours=1),
            closed_at=cls.base+timedelta(hours=1),
            tier_index=0, starting_capital_usd=Decimal("100.00"),
        )
        PropEquityObservation.objects.create(
            account=cls.account, external_event_id="C145-session-open",
            observed_at=cls.base, equity_usd=Decimal("100.00"),
            is_session_open=True, reconciliation_status="verified",
            data_source="synthetic-ci-only",
        )
        PropExecution.objects.create(
            account=cls.account, external_event_id="C145-closed-position",
            external_position_id="C145-position-1",
            data_source="synthetic-ci-only", execution_origin="manual",
            symbol="XAUUSD", closed_at=cls.base+timedelta(minutes=10),
            gross_realized_usd=Decimal("1.00"),
            total_fees_usd=Decimal("0.00"),
            reconciliation_status="verified",
        )
        PropEquityObservation.objects.create(
            account=cls.account, external_event_id="C145-session-close",
            observed_at=cls.base+timedelta(minutes=20),
            equity_usd=Decimal("101.00"), reconciliation_status="verified",
            data_source="synthetic-ci-only",
        )

    def denied(self):
        row = account_projection(self.account)
        self.assertEqual(row["net_profit"], Decimal("1.00"))
        self.assertFalse(row["purchase_window_valid"])
        self.assertFalse(row["verified"])
        self.assertEqual(row["evidence_state"], "pending")
        self.assertIsNotNone(row["assessment"])
        self.assertFalse(row["assessment"].passed)

    def test_01_synthetic_consistent_purchase_keeps_evidence_reconciled(self):
        row = account_projection(self.account)
        self.assertTrue(row["purchase_window_valid"])
        self.assertTrue(row["verified"])
        self.assertEqual(row["evidence_state"], "reconciled")
        self.assertFalse(row["assessment"].passed)  # never bypass 6-day rule

    def test_02_unsettled_purchase_never_displays_verified(self):
        PropChallengeEnrollment.objects.filter(pk=self.purchase.pk).update(
            settlement_verified=False
        )
        self.denied()

    def test_03_wrong_plan_tier_never_displays_verified(self):
        PropChallengeEnrollment.objects.filter(pk=self.purchase.pk).update(
            plan_code="MOJ-PROP-06"
        )
        self.denied()

    def test_04_unrelated_buyer_receipt_never_displays_verified(self):
        user = get_user_model().objects.create_user(
            username="c145_unrelated", password="CI-only"
        )
        foreign = PropTrader.objects.create(user=user)
        PropChallengeEnrollment.objects.filter(pk=self.purchase.pk).update(
            trader=foreign
        )
        self.denied()

    def test_05_future_purchase_never_displays_verified(self):
        PropChallengeEnrollment.objects.filter(pk=self.purchase.pk).update(
            confirmed_at=timezone.now()+timedelta(days=1)
        )
        self.denied()

    def test_06_expired_purchase_window_never_displays_verified(self):
        PropChallengeEnrollment.objects.filter(pk=self.purchase.pk).update(
            confirmed_at=self.base-timedelta(days=29)
        )
        self.denied()

    def test_07_mutated_account_capital_never_displays_verified(self):
        PropAccount.objects.filter(pk=self.account.pk).update(
            starting_capital_usd=Decimal("200.00")
        )
        self.account.refresh_from_db()
        self.denied()

    def test_08_account_started_after_trade_never_displays_verified(self):
        PropAccount.objects.filter(pk=self.account.pk).update(
            opened_at=self.base+timedelta(minutes=11)
        )
        self.account.refresh_from_db()
        self.denied()

    def test_09_account_closed_before_trade_never_displays_verified(self):
        PropAccount.objects.filter(pk=self.account.pk).update(
            closed_at=self.base+timedelta(minutes=5)
        )
        self.account.refresh_from_db()
        self.denied()

    def test_10_missing_purchase_never_displays_verified(self):
        PropAccount.objects.filter(pk=self.account.pk).update(
            challenge_enrollment=None
        )
        self.account.refresh_from_db()
        self.denied()
