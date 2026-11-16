"""The purchased plan, not global plan 1, controls simulated P&L targets."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from prop_firm.models import (
    PropTrader, PropChallengeEnrollment, PropAccount,
    PropExecution, PropEquityObservation,
)
from prop_firm.portal import account_projection

START=datetime(2026,10,1,0,0,tzinfo=timezone.utc)


class PurchasedPlanQualificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user=get_user_model().objects.create_user(
            username="ten_plan_qualification",password="ci-only")
        cls.trader=PropTrader.objects.create(user=user)
        cls.purchase=PropChallengeEnrollment.objects.create(
            trader=cls.trader,verified_invoice_ref="ci-plan-06-settled",
            plan_code="MOJ-PROP-06",confirmed_at=START,
            settlement_verified=True,
        )
        cls.account=PropAccount.objects.create(
            trader=cls.trader,challenge_enrollment=cls.purchase,
            kind=PropAccount.Kind.PHASE_ONE,
            status=PropAccount.Status.ACTIVE,
            tier_index=5,starting_capital_usd=Decimal("3000"),
            reconciled_by_operator=True,
        )

    def six_days_at_plan6(self):
        for n in range(6):
            moment=START+timedelta(days=n,hours=12)
            base=Decimal("3000")+Decimal(n)*Decimal("48")
            PropEquityObservation.objects.create(
                account=self.account,external_event_id=f"open-{n}",
                observed_at=moment-timedelta(hours=4),
                is_session_open=True,equity_usd=base,
                reconciliation_status="verified",
            )
            PropExecution.objects.create(
                account=self.account,
                external_event_id=f"execution-{n}",
                external_position_id=f"broker-position-{n}",
                data_source="broker-ci",symbol="XAUUSD",
                closed_at=moment,gross_realized_usd=Decimal("48"),
                total_fees_usd=0,reconciliation_status="verified",
                execution_origin="bot",
            )
            PropEquityObservation.objects.create(
                account=self.account,external_event_id=f"close-{n}",
                observed_at=moment+timedelta(hours=2),
                is_session_open=False,equity_usd=base+Decimal("48"),
                reconciliation_status="verified",
            )

    def test_phase_one_profit_target_scales_to_purchased_3000_capital(self):
        self.six_days_at_plan6()
        data=account_projection(self.account)
        self.assertTrue(data["verified"])
        self.assertEqual(data["plan_code"],"MOJ-PROP-06")
        self.assertEqual(data["selected_plan"].starting_capital_usd,Decimal("3000"))
        self.assertEqual(data["assessment"].goal_usd,Decimal("288"))
        self.assertTrue(data["assessment"].passed)
        self.assertEqual(data["challenge_trade_count"].valid_closed_positions,6)
        self.assertEqual(data["challenge_trade_count"].bot_positions,6)

    def test_tampering_tier_after_purchase_fails_closed(self):
        self.six_days_at_plan6()
        PropAccount.objects.filter(pk=self.account.pk).update(
            starting_capital_usd=Decimal("100"),tier_index=0
        )
        self.account.refresh_from_db()
        data=account_projection(self.account)
        self.assertFalse(data["purchase_window_valid"])
        self.assertFalse(data["assessment"].passed)
        self.assertIn("reconciled_evidence_required",data["assessment"].reasons)

    def test_no_reusing_an_unrelated_tier_as_purchase_proof(self):
        self.six_days_at_plan6()
        PropChallengeEnrollment.objects.filter(pk=self.purchase.pk).update(
            plan_code="MOJ-PROP-10"
        )
        self.purchase.refresh_from_db()
        data=account_projection(self.account)
        self.assertFalse(data["purchase_window_valid"])
        self.assertFalse(data["assessment"].passed)

    def test_c143_equity_before_paid_purchase_cannot_qualify(self):
        self.six_days_at_plan6()
        PropEquityObservation.objects.filter(
            account=self.account, external_event_id="open-0"
        ).update(observed_at=START-timedelta(seconds=1))
        data=account_projection(self.account)
        self.assertFalse(data["purchase_window_valid"])
        self.assertFalse(data["assessment"].passed)
        self.assertIn("reconciled_evidence_required", data["assessment"].reasons)

    def test_c143_equity_exactly_at_paid_start_is_in_window(self):
        self.six_days_at_plan6()
        PropEquityObservation.objects.filter(
            account=self.account, external_event_id="open-0"
        ).update(observed_at=START)
        data=account_projection(self.account)
        self.assertTrue(data["purchase_window_valid"])
        self.assertTrue(data["assessment"].passed)

    def test_c143_equity_exactly_at_28_day_deadline_is_excluded(self):
        self.six_days_at_plan6()
        PropEquityObservation.objects.filter(
            account=self.account, external_event_id="close-5"
        ).update(observed_at=START+timedelta(days=28))
        data=account_projection(self.account)
        self.assertFalse(data["purchase_window_valid"])
        self.assertFalse(data["assessment"].passed)

    def test_c143_equity_one_second_before_deadline_is_within_window(self):
        self.six_days_at_plan6()
        PropEquityObservation.objects.filter(
            account=self.account, external_event_id="close-5"
        ).update(observed_at=START+timedelta(days=28)-timedelta(seconds=1))
        data=account_projection(self.account)
        self.assertTrue(data["purchase_window_valid"])

    def test_c143_historical_cutoff_excludes_post_cutoff_equity(self):
        self.six_days_at_plan6()
        PropEquityObservation.objects.create(
            account=self.account, external_event_id="late-mark",
            observed_at=START+timedelta(days=29),
            is_session_open=False, equity_usd=Decimal("3288"),
            reconciliation_status="verified",
        )
        # The current projection must reject the full stream.
        self.assertFalse(account_projection(self.account)["purchase_window_valid"])
        # An earlier historical projection must not inspect future events.
        data=account_projection(
            self.account, evidence_cutoff=START+timedelta(days=7)
        )
        self.assertTrue(data["purchase_window_valid"])
