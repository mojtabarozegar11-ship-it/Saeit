"""C144 — future broker evidence may not forge funding qualification.

All rows are artificial Django test fixtures; none originate from a real
broker, blockchain, buyer or settled challenge.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone as django_timezone

from prop_firm.models import (
    PropAccount, PropChallengeEnrollment, PropEquityObservation,
    PropExecution, PropTrader,
)
from prop_firm.portal import account_projection


class FutureEvidenceQualificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user(
            username="c144_isolated_buyer", password="CI-only-never-live"
        )
        cls.trader = PropTrader.objects.create(user=user)
        cls.account = PropAccount.objects.create(
            trader=cls.trader,
            kind=PropAccount.Kind.PHASE_ONE,
            reconciled_by_operator=True,
        )

    def trade(self, event, when, *, account=None, amount="5.00", position=None):
        return PropExecution.objects.create(
            account=account or self.account,
            external_event_id=event,
            external_position_id=position or event,
            data_source="test-only-simulator",
            symbol="XAUUSD",
            closed_at=when,
            gross_realized_usd=Decimal(amount),
            total_fees_usd=Decimal("0"),
            reconciliation_status="verified",
            execution_origin="manual",
        )

    def mark(self, event, when, value, *, opened=False):
        return PropEquityObservation.objects.create(
            account=self.account,
            external_event_id=event,
            data_source="test-only-simulator",
            observed_at=when,
            equity_usd=Decimal(value),
            is_session_open=opened,
            reconciliation_status="verified",
        )

    def test_01_future_verified_trade_cannot_create_present_net_profit(self):
        self.trade("future-execution", django_timezone.now()+timedelta(days=1))
        projection = account_projection(self.account)
        self.assertEqual(projection["net_profit"], Decimal("0"))
        self.assertEqual(projection["trading_days"], 0)
        self.assertFalse(projection["verified"])

    def test_02_future_trade_cannot_reinflate_already_reconciled_profit(self):
        now = django_timezone.now()
        self.mark("past-open", now-timedelta(hours=3), "100", opened=True)
        self.mark("past-close", now-timedelta(hours=1), "105")
        self.trade("past-trade", now-timedelta(hours=2), amount="5")
        self.trade("future-trade", now+timedelta(days=1), amount="100000")
        projection = account_projection(self.account)
        self.assertEqual(projection["net_profit"], Decimal("5.00"))
        self.assertFalse(projection["verified"])

    def test_03_future_verified_equity_cannot_raise_current_equity(self):
        now = django_timezone.now()
        self.mark("opening", now-timedelta(hours=3), "100", opened=True)
        self.mark("past-close", now-timedelta(hours=1), "104")
        self.mark("future-close", now+timedelta(days=1), "100000")
        self.trade("past-close-trade", now-timedelta(hours=2), amount="4")
        projection = account_projection(self.account)
        self.assertEqual(projection["last_equity"], Decimal("104"))
        self.assertFalse(projection["verified"])

    def test_04_historical_as_of_excludes_later_trades(self):
        now = django_timezone.now()
        old = now-timedelta(days=3)
        new = now-timedelta(hours=2)
        self.trade("old-trade", old, amount="7")
        self.trade("newer-trade", new, amount="40")
        projected = account_projection(self.account, as_of=now-timedelta(days=1))
        self.assertEqual(projected["net_profit"], Decimal("7.00"))
        self.assertEqual(projected["trading_days"], 1)

    def test_05_future_as_of_does_not_unlock_future_trades(self):
        now = django_timezone.now()
        self.trade("unrealized-future-trade", now+timedelta(days=1), amount="5000")
        projected = account_projection(self.account, as_of=now+timedelta(days=40))
        self.assertEqual(projected["net_profit"], Decimal("0"))
        self.assertFalse(projected["verified"])

    def test_06_naive_as_of_rejected_before_query(self):
        with self.assertRaisesRegex(ValueError, "as_of must be timezone-aware"):
            account_projection(self.account, as_of=datetime(2026, 11, 16))

    def test_07_naive_evidence_cutoff_rejected_before_query(self):
        with self.assertRaisesRegex(ValueError, "evidence_cutoff must be timezone-aware"):
            account_projection(self.account, evidence_cutoff=datetime(2026, 11, 16))

    def test_08_historical_evidence_cutoff_remains_exclusive(self):
        now = django_timezone.now()
        earlier = now-timedelta(days=2)
        cutoff = now-timedelta(days=1)
        self.trade("included", earlier, amount="3")
        self.trade("at-cutoff", cutoff, amount="70")
        projected = account_projection(self.account, evidence_cutoff=cutoff)
        self.assertEqual(projected["net_profit"], Decimal("3.00"))

    def _purchased_cohort(self, *, paid_at):
        purchase = PropChallengeEnrollment.objects.create(
            trader=self.trader,
            verified_invoice_ref="C144-SYNTHETIC-NOT-SETTLED",
            plan_code="MOJ-PROP-01",
            confirmed_at=paid_at,
            settlement_verified=True,  # synthetic fixture ONLY
        )
        phase1 = PropAccount.objects.create(
            trader=self.trader,
            kind=PropAccount.Kind.PHASE_ONE,
            challenge_enrollment=purchase,
        )
        phase2 = PropAccount.objects.create(
            trader=self.trader,
            kind=PropAccount.Kind.PHASE_TWO,
            challenge_enrollment=purchase,
        )
        return phase1, phase2

    def test_09_future_trade_in_other_phase_not_fiftieth_position(self):
        now = django_timezone.now()
        phase1, phase2 = self._purchased_cohort(paid_at=now-timedelta(days=3))
        rows = [
            PropExecution(
                account=phase1, external_event_id=f"valid-{i}",
                external_position_id=f"position-{i}",
                data_source="test-only-simulator",
                symbol="XAUUSD", closed_at=now-timedelta(hours=5),
                gross_realized_usd=Decimal("1"),
                reconciliation_status="verified",
                execution_origin="bot",
            ) for i in range(49)
        ]
        rows.append(PropExecution(
            account=phase1, external_event_id="future-fiftieth",
            external_position_id="position-49",
            data_source="test-only-simulator",
            symbol="XAUUSD", closed_at=now+timedelta(days=1),
            gross_realized_usd=Decimal("1"),
            reconciliation_status="verified",
            execution_origin="bot",
        ))
        PropExecution.objects.bulk_create(rows)
        result = account_projection(phase2)
        self.assertEqual(result["challenge_trade_count"].valid_closed_positions, 49)
        self.assertFalse(result["challenge_trade_count"].sufficient)

    def test_10_as_of_excludes_other_phase_late_fiftieth_position(self):
        now = django_timezone.now()
        phase1, phase2 = self._purchased_cohort(paid_at=now-timedelta(days=6))
        cutoff = now-timedelta(days=1)
        rows = [
            PropExecution(
                account=phase1, external_event_id=f"old-{i}",
                external_position_id=f"position-{i}",
                data_source="test-only-simulator", symbol="XAUUSD",
                closed_at=now-timedelta(days=2),
                gross_realized_usd=Decimal("1"),
                reconciliation_status="verified", execution_origin="bot",
            ) for i in range(49)
        ]
        rows.append(PropExecution(
            account=phase1, external_event_id="late-fiftieth",
            external_position_id="position-49",
            data_source="test-only-simulator", symbol="XAUUSD",
            closed_at=now-timedelta(hours=3),
            gross_realized_usd=Decimal("1"),
            reconciliation_status="verified", execution_origin="bot",
        ))
        PropExecution.objects.bulk_create(rows)
        result = account_projection(phase2, as_of=cutoff)
        self.assertEqual(result["challenge_trade_count"].valid_closed_positions, 49)
        self.assertFalse(result["challenge_trade_count"].sufficient)

    def test_11_future_as_of_cannot_complete_required_28_day_social_window(self):
        now = django_timezone.now()
        _, phase2 = self._purchased_cohort(paid_at=now-timedelta(days=3))
        result = account_projection(phase2, as_of=now+timedelta(days=60))
        self.assertFalse(result["social_posting"].challenge_window_complete)
        self.assertFalse(result["social_posting"].satisfied)


    def test_12_future_purchase_claim_cannot_trigger_social_or_qualification(self):
        now = django_timezone.now()
        _, phase2 = self._purchased_cohort(paid_at=now-timedelta(days=3))
        PropChallengeEnrollment.objects.filter(
            pk=phase2.challenge_enrollment_id
        ).update(confirmed_at=now+timedelta(days=2))
        result = account_projection(phase2)
        self.assertFalse(result["purchase_window_valid"])
        self.assertIsNone(result["social_posting"])

    def test_13_as_of_before_purchase_cannot_evaluate_paid_challenge(self):
        now = django_timezone.now()
        _, phase2 = self._purchased_cohort(paid_at=now-timedelta(days=1))
        result = account_projection(phase2, as_of=now-timedelta(days=2))
        self.assertFalse(result["purchase_window_valid"])
        self.assertIsNone(result["challenge_trade_count"])

    def test_14_past_purchased_challenge_remains_within_window(self):
        now = django_timezone.now()
        _, phase2 = self._purchased_cohort(paid_at=now-timedelta(days=3))
        result = account_projection(phase2, as_of=now-timedelta(days=1))
        self.assertTrue(result["purchase_window_valid"])
        self.assertIsNotNone(result["social_posting"])

    def test_15_naive_confirmed_at_on_fetched_model_is_not_trusted(self):
        now = django_timezone.now()
        _, phase2 = self._purchased_cohort(paid_at=now-timedelta(days=3))
        purchase = phase2.challenge_enrollment
        purchase.confirmed_at = datetime(2026, 11, 16)
        result = account_projection(phase2)
        self.assertFalse(result["purchase_window_valid"])

    def test_16_future_as_of_cannot_override_future_purchase(self):
        now = django_timezone.now()
        _, phase2 = self._purchased_cohort(paid_at=now-timedelta(days=3))
        PropChallengeEnrollment.objects.filter(
            pk=phase2.challenge_enrollment_id
        ).update(confirmed_at=now+timedelta(days=1))
        result = account_projection(phase2, as_of=now+timedelta(days=35))
        self.assertFalse(result["purchase_window_valid"])

    def test_17_evidence_cutoff_before_paid_enrollment_is_not_a_sale(self):
        now = django_timezone.now()
        _, phase2 = self._purchased_cohort(paid_at=now-timedelta(days=2))
        result = account_projection(
            phase2, evidence_cutoff=now-timedelta(days=3)
        )
        self.assertFalse(result["purchase_window_valid"])
        self.assertIsNone(result["challenge_trade_count"])


if __name__ == "__main__":
    import unittest
    unittest.main()
