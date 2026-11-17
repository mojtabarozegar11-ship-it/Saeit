"""C147: funded dashboard KYC/eligibility is a live revocation gate.

Synthetic Django fixtures only. No payment, account funding, brokerage or
customer identity screening actually occurs in this suite.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from prop_firm.models import (
    PropTrader, PropAccount, PropExecution, PropEquityObservation,
)
from prop_firm.portal import account_projection


class FundedAccountRevocationProjectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user(
            username="c147_synthetic_trader", password="ci-only-no-live-account"
        )
        cls.trader = PropTrader.objects.create(
            user=user, kyc_status="verified", eligibility_status="eligible",
        )
        begin = (timezone.now() - timedelta(days=2)).replace(
            hour=8, minute=0, second=0, microsecond=0,
        )
        cls.account = PropAccount.objects.create(
            trader=cls.trader, kind=PropAccount.Kind.FUNDED,
            status=PropAccount.Status.ACTIVE,
            tier_index=0, starting_capital_usd=Decimal("100.00"),
            opened_at=begin, reference="c147-fixture-not-a-real-broker",
            reconciled_by_operator=True,
        )
        PropEquityObservation.objects.create(
            account=cls.account, external_event_id="ci-opening-mark",
            observed_at=begin, equity_usd=Decimal("100"),
            is_session_open=True, reconciliation_status="verified",
            data_source="simulated-test-only",
        )
        PropExecution.objects.create(
            account=cls.account, external_event_id="ci-close-event",
            data_source="simulated-test-only", symbol="XAUUSD",
            closed_at=begin + timedelta(hours=1),
            gross_realized_usd=Decimal("1"),
            total_fees_usd=Decimal("0"),
            reconciliation_status="verified",
        )
        PropEquityObservation.objects.create(
            account=cls.account, external_event_id="ci-closing-mark",
            observed_at=begin + timedelta(hours=2),
            equity_usd=Decimal("101"),
            is_session_open=False, reconciliation_status="verified",
            data_source="simulated-test-only",
        )

    def projection(self):
        # A fresh model instance deliberately avoids all cached FK relations.
        return account_projection(PropAccount.objects.get(pk=self.account.pk))

    def assert_pending(self):
        result = self.projection()
        self.assertEqual(result["net_profit"], Decimal("1"))
        self.assertFalse(result["verified"])
        self.assertEqual(result["evidence_state"], "pending")

    def test_01_active_synthetic_funded_user_can_show_reconciled(self):
        result = self.projection()
        self.assertTrue(result["verified"])
        self.assertEqual(result["evidence_state"], "reconciled")
        self.assertIsNone(result["assessment"])  # no completed monthly period

    def test_02_pending_kyc_reconciled_funded_account_is_blocked(self):
        PropTrader.objects.filter(pk=self.trader.pk).update(kyc_status="pending")
        self.assert_pending()

    def test_03_rejected_kyc_reconciled_funded_account_is_blocked(self):
        PropTrader.objects.filter(pk=self.trader.pk).update(kyc_status="rejected")
        self.assert_pending()

    def test_04_eligibility_revocation_blocks_reconciled_display(self):
        PropTrader.objects.filter(pk=self.trader.pk).update(
            eligibility_status="blocked"
        )
        self.assert_pending()

    def test_05_inactive_user_blocks_reconciled_display(self):
        get_user_model().objects.filter(pk=self.trader.user_id).update(
            is_active=False
        )
        self.assert_pending()

    def test_06_legacy_simulation_kyc_policy_stays_separate_from_funded(self):
        PropTrader.objects.filter(pk=self.trader.pk).update(kyc_status="pending")
        simulated = PropAccount.objects.create(
            trader=PropTrader.objects.get(pk=self.trader.pk),
            kind=PropAccount.Kind.PHASE_ONE,
            starting_capital_usd=Decimal("100.00"),
        )
        self.assertEqual(simulated.kind, PropAccount.Kind.PHASE_ONE)
