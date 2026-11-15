"""Moj Prop provisional allocations are append-only memo entries, never payouts."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from prop_firm.allocation_service import AllocationRejected, stage_provisional_allocation
from prop_firm.models import (
    PropAccount, PropTrader, PropExecution, PropEquityObservation,
    PropProfitAllocation, PropProfitJournalLine,
)
from prop_firm.rules import POLICY

OPENED = datetime(2026, 1, 1, tzinfo=timezone.utc)
EVIDENCE_KEY = "verified-signing-key-only-in-tests-not-used-for-transfers"


@override_settings(MOJ_PROP_TRUSTED_EVIDENCE_KEYS={"broker_fixture": EVIDENCE_KEY})
class MojPropProvisionalAllocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user(
            username="allocation_test_user", password="not-a-real-credential"
        )
        cls.trader = PropTrader.objects.create(
            user=user, kyc_status="verified", eligibility_status="eligible"
        )
        cls.account = PropAccount.objects.create(
            trader=cls.trader, kind=PropAccount.Kind.FUNDED,
            status=PropAccount.Status.ACTIVE,
            tier_index=0, starting_capital_usd=Decimal("100.00"),
            opened_at=OPENED, reference="broker-demo-reference-only",
            reconciled_by_operator=True, policy_version=POLICY.version,
        )

    def trade_day(self, *, day=10, pnl="3.00", source="broker_fixture",
                  status="verified", digest="a" * 64, identifier=None,
                  initial_equity="100", final_equity="103"):
        event_id = identifier or f"execution-{day}"
        date = OPENED + timedelta(days=day)
        PropExecution.objects.create(
            account=self.account, data_source=source, external_event_id=event_id,
            symbol="EURUSD", closed_at=date + timedelta(hours=13),
            gross_realized_usd=Decimal(pnl), total_fees_usd=Decimal("0"),
            reconciliation_status=status, evidence_digest=digest,
        )
        PropEquityObservation.objects.create(
            account=self.account, data_source=source, external_event_id=f"open-{day}",
            observed_at=date + timedelta(hours=8),
            equity_usd=Decimal(initial_equity), is_session_open=True,
            reconciliation_status="verified", evidence_digest="b" * 64,
        )
        PropEquityObservation.objects.create(
            account=self.account, data_source=source, external_event_id=f"close-{day}",
            observed_at=date + timedelta(hours=14),
            equity_usd=Decimal(final_equity), is_session_open=False,
            reconciliation_status="verified", evidence_digest="c" * 64,
        )

    def stage(self, day=30):
        return stage_provisional_allocation(
            account_id=self.account.pk, as_of=OPENED + timedelta(days=day),
        )

    def test_equity_marks_without_allowlisted_source_never_stage_profit(self):
        for bad_source in ("", "untrusted_broker", "broker_fixture_injected"):
            with self.subTest(source=bad_source):
                PropExecution.objects.all().delete()
                PropEquityObservation.objects.all().delete()
                self.trade_day()
                PropEquityObservation.objects.filter(account=self.account).update(
                    data_source=bad_source,
                )
                with self.assertRaises(AllocationRejected):
                    self.stage()

    def test_equity_mark_from_other_source_blocks_allocation_even_with_valid_digest(self):
        self.trade_day()
        PropEquityObservation.objects.filter(
            account=self.account, is_session_open=False,
        ).update(data_source="other_registered_source", evidence_digest="a" * 64)
        with self.assertRaises(AllocationRejected):
            self.stage()

    def test_valid_verified_month_stages_only_provisional_distribution(self):
        self.trade_day()
        a = self.stage()
        self.assertEqual(a.status, "provisional")
        self.assertEqual((a.eligible_profit_usd,a.trader_profit_usd,a.company_profit_usd),
                         (Decimal("3.00"), Decimal("2.10"), Decimal("0.90")))
        self.assertEqual(a.cumulative_realized_net_usd, Decimal("3.00"))
        self.assertEqual(a.period_number, 1)
        self.assertEqual(PropProfitJournalLine.objects.count(), 3)

    def test_journal_entries_balance_and_are_not_cash_transactions(self):
        self.trade_day()
        a = self.stage()
        lines = list(PropProfitJournalLine.objects.filter(allocation=a))
        debits = sum((x.amount_usd for x in lines if x.side == "debit"),Decimal("0"))
        credits = sum((x.amount_usd for x in lines if x.side == "credit"),Decimal("0"))
        self.assertEqual(debits, credits)
        self.assertEqual(debits, a.eligible_profit_usd)
        self.assertNotIn("paid", {x.code for x in lines})

    def test_identical_period_idempotent(self):
        self.trade_day()
        first = self.stage()
        second = self.stage()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(PropProfitAllocation.objects.count(), 1)
        self.assertEqual(PropProfitJournalLine.objects.count(), 3)

    def test_same_period_modified_history_rejected(self):
        self.trade_day()
        self.stage()
        PropExecution.objects.filter(account=self.account).update(
            gross_realized_usd=Decimal("3.5")
        )
        with self.assertRaises(AllocationRejected):
            self.stage()

    def test_unfinished_period_rejected(self):
        self.trade_day()
        with self.assertRaises(AllocationRejected):
            self.stage(29)

    def test_empty_period_rejected(self):
        with self.assertRaises(AllocationRejected):
            self.stage()

    def test_second_period_cannot_skip_first(self):
        self.trade_day()
        # A delayed month-one reconciliation must be accepted rather than lost.
        with self.assertRaises(AllocationRejected):
            stage_provisional_allocation(
                account_id=self.account.pk, as_of=OPENED + timedelta(days=60),
                period_number=2,
            )
        first = self.stage(60)
        self.assertEqual(first.period_number, 1)
        self.assertEqual(first.eligible_profit_usd, Decimal("3.00"))

    def test_rejected_kyc_blocks_allocation(self):
        self.trade_day()
        self.trader.kyc_status = "pending"
        self.trader.save()
        with self.assertRaises(AllocationRejected):
            self.stage()

    def test_unqualified_country_blocks_allocation(self):
        self.trade_day()
        self.trader.eligibility_status = "blocked"
        self.trader.save()
        with self.assertRaises(AllocationRejected):
            self.stage()

    def test_simulated_accounts_not_eligible(self):
        self.trade_day()
        self.account.kind = PropAccount.Kind.PHASE_ONE
        self.account.reference = ""
        self.account.save()
        with self.assertRaises(AllocationRejected):
            self.stage()

    def test_account_closed_blocks_allocation(self):
        self.trade_day()
        self.account.status = PropAccount.Status.CLOSED
        self.account.save()
        with self.assertRaises(AllocationRejected):
            self.stage()

    def test_no_operator_reconciliation_blocks_allocation(self):
        self.trade_day()
        self.account.reconciled_by_operator = False
        self.account.save()
        with self.assertRaises(AllocationRejected):
            self.stage()

    def test_policy_version_mismatch_blocks_allocation(self):
        self.trade_day()
        self.account.policy_version = "unknown/legacy"
        self.account.save()
        with self.assertRaises(AllocationRejected):
            self.stage()

    def test_untrusted_source_blocks_allocation(self):
        self.trade_day(source="untrusted")
        with self.assertRaises(AllocationRejected):
            self.stage()

    def test_missing_signed_trade_evidence_blocks_allocation(self):
        self.trade_day(digest="")
        with self.assertRaises(AllocationRejected):
            self.stage()

    def test_pending_trade_blocks_allocation(self):
        self.trade_day(status="pending")
        with self.assertRaises(AllocationRejected):
            self.stage()

    def test_no_approved_broker_sources_blocks_allocation(self):
        self.trade_day()
        with override_settings(MOJ_PROP_TRUSTED_EVIDENCE_KEYS={}):
            with self.assertRaises(AllocationRejected):
                self.stage()

    def test_ledger_does_not_create_customer_payment_or_wallet_record(self):
        self.trade_day()
        self.stage()
        self.assertEqual(PropProfitAllocation.objects.filter(status="provisional").count(), 1)
        self.assertEqual(PropProfitAllocation.objects.exclude(status="provisional").count(), 0)

    def test_loss_month_creates_no_allocable_credit_then_recovery(self):
        self.trade_day(day=10, pnl="3", initial_equity="100", final_equity="103")
        a1=self.stage(30)
        self.trade_day(day=40, pnl="-2", initial_equity="103", final_equity="101")
        a2=self.stage(60)
        self.assertEqual(a2.cumulative_realized_net_usd, Decimal("1"))
        self.assertEqual(a2.eligible_profit_usd, 0)
        self.assertEqual(a2.journal_lines.count(), 0)
        self.trade_day(day=70, pnl="4", initial_equity="101", final_equity="105")
        a3=self.stage(90)
        self.assertEqual(a3.cumulative_realized_net_usd, Decimal("5"))
        self.assertEqual(a3.previously_allocated_usd, Decimal("3"))
        self.assertEqual((a3.eligible_profit_usd,a3.trader_profit_usd,a3.company_profit_usd),
                         (Decimal("2"),Decimal("1.40"),Decimal(".60")))
        self.assertEqual(sum(x.eligible_profit_usd for x in
                         PropProfitAllocation.objects.all()), Decimal("5"))

    def test_zero_profit_loss_carryover_does_not_create_journal(self):
        self.trade_day(pnl="-1", initial_equity="100", final_equity="99")
        a=self.stage()
        self.assertEqual(a.eligible_profit_usd, 0)
        self.assertEqual(a.trader_profit_usd, 0)
        self.assertEqual(a.company_profit_usd, 0)
        self.assertFalse(a.journal_lines.exists())

    def test_trader_profit_rounds_down_without_imbalance(self):
        self.trade_day(pnl=".01", initial_equity="100", final_equity="100.01")
        a=self.stage()
        self.assertEqual(a.eligible_profit_usd, Decimal(".01"))
        self.assertEqual(a.trader_profit_usd, Decimal("0.00"))
        self.assertEqual(a.company_profit_usd, Decimal(".01"))
        self.assertEqual(a.journal_lines.count(), 2)


    def test_late_processing_of_three_months_preserves_every_period(self):
        self.trade_day(day=10, pnl="3", initial_equity="100", final_equity="103")
        self.trade_day(day=40, pnl="-2", initial_equity="103", final_equity="101")
        self.trade_day(day=70, pnl="4", initial_equity="101", final_equity="105")
        first = self.stage(90)
        second = self.stage(90)
        third = self.stage(90)
        self.assertEqual([first.period_number, second.period_number, third.period_number],
                         [1, 2, 3])
        self.assertEqual([first.eligible_profit_usd, second.eligible_profit_usd,
                          third.eligible_profit_usd],
                         [Decimal("3"), Decimal("0"), Decimal("2")])
        self.assertEqual(PropProfitAllocation.objects.count(), 3)
        self.assertEqual(self.stage(90).pk, third.pk)

    def test_early_future_evidence_does_not_pollute_past_month(self):
        self.trade_day(day=10, pnl="3", initial_equity="100", final_equity="103")
        PropExecution.objects.create(
            account=self.account, external_event_id="future-pending", data_source="untrusted",
            symbol="FUTURE", closed_at=OPENED + timedelta(days=45),
            gross_realized_usd=999, total_fees_usd=0,
            reconciliation_status="pending", evidence_digest="",
        )
        a = self.stage(60)
        self.assertEqual(a.period_number, 1)
        self.assertEqual(a.eligible_profit_usd, Decimal("3.00"))
        # The next stage still must reject untrusted/unverified later events.
        with self.assertRaises(AllocationRejected):
            self.stage(60)

    def test_same_profit_with_tampered_symbol_fails_closed(self):
        self.trade_day(day=10, pnl="3")
        self.stage(30)
        PropExecution.objects.filter(account=self.account).update(symbol="CHANGED")
        with self.assertRaises(AllocationRejected):
            self.stage(30)

    def test_same_profit_with_tampered_equity_mark_fails_closed(self):
        self.trade_day(day=10, pnl="3")
        self.stage(30)
        PropEquityObservation.objects.filter(
            account=self.account, is_session_open=False
        ).update(equity_usd=Decimal("102.5"))
        with self.assertRaises(AllocationRejected):
            self.stage(30)

    def test_requested_month_zero_bool_or_float_refused(self):
        self.trade_day()
        for invalid in (0, -1, True, 1.0, "1"):
            with self.subTest(invalid=invalid), self.assertRaises(AllocationRejected):
                stage_provisional_allocation(
                    account_id=self.account.pk,
                    as_of=OPENED + timedelta(days=60),
                    period_number=invalid,
                )

    def test_skipping_a_month_is_refused_even_after_ninety_days(self):
        self.trade_day()
        with self.assertRaises(AllocationRejected):
            stage_provisional_allocation(
                account_id=self.account.pk,
                as_of=OPENED + timedelta(days=90),
                period_number=3,
            )

    def test_unfinished_selected_future_month_is_refused(self):
        self.trade_day()
        with self.assertRaises(AllocationRejected):
            stage_provisional_allocation(
                account_id=self.account.pk,
                as_of=OPENED + timedelta(days=30),
                period_number=2,
            )

    def test_existing_older_period_cannot_be_replayed_after_next_recorded(self):
        self.trade_day(day=10, pnl="3")
        a1 = self.stage(30)
        a2 = self.stage(60)
        self.assertEqual(a2.period_number, 2)
        with self.assertRaises(AllocationRejected):
            stage_provisional_allocation(
                account_id=self.account.pk,
                as_of=OPENED + timedelta(days=60),
                period_number=1,
            )
        self.assertEqual(a1.period_number, 1)
