"""Real deterministic unit checks for the per-tenant virtual fill ledger.

This is source-unit testing, never a live HTTP, MariaDB, or broker execution.
"""
from dataclasses import replace, FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from prop_firm.plan1_v14_social_or_50_terms import review_prospective_terms
from prop_firm.plan1_v141_virtual_tenant_fill_ledger import (
    ProvisionedVirtualChallenge, VirtualFill, VirtualLedgerRejected,
    replay_provisioned_virtual_books,
)

NOW = datetime(2026, 11, 17, 17, 0, tzinfo=timezone.utc)
START = NOW - timedelta(days=2)
SHA = "a" * 64


def provision(n=1, **change):
    args = dict(trader_ref=f"TRADER-{n}",
                challenge_ref=f"CHALLENGE-{n}",
                terms_sha256=review_prospective_terms().contract_candidate_sha256,
                opened_at_utc=START, max_unlocked_stage=1,
                trusted_feed_source="MOJ-SIM-VERIFIED-SERVER")
    args.update(change)
    return ProvisionedVirtualChallenge(**args)


def event(n=1, seq=1, *, action="OPEN", direction="BUY", stage=1,
          price="3000", qty="1", position=None, **change):
    args = dict(trader_ref=f"TRADER-{n}",
                challenge_ref=f"CHALLENGE-{n}",
                event_id=f"EVENT-{n}-{seq}",
                sequence=seq,
                position_ref=position or f"POSITION-{n}",
                stage=stage, action=action, direction=direction,
                symbol="XAUUSD", quantity_ounces=qty,
                price_usd_per_ounce=price, fee_usd="0.10",
                executed_at_utc=START + timedelta(minutes=seq),
                feed_source="MOJ-SIM-VERIFIED-SERVER",
                raw_event_sha256=SHA)
    args.update(change)
    return VirtualFill(**args)


def run(*events, provisioned=None, server_now=NOW):
    return replay_provisioned_virtual_books(
        challenges=tuple(provisioned if provisioned is not None else (provision(),)),
        events=tuple(events), server_now=server_now)


class VirtualTenantLedgerUnitTests(unittest.TestCase):
    def test_01_empty_registry_is_safe(self):
        out=run(provisioned=())
        self.assertEqual(out.challenge_books,())
        self.assertEqual(out.company_real_broker_orders_emitted,0)

    def test_02_provisioned_challenge_without_trades_is_zero_not_broker(self):
        b=run().challenge_books[0]
        self.assertEqual(b.cash_balance_excluding_unrealized_usd,Decimal("100"))
        self.assertEqual(b.fully_closed_positions_total,0)
        self.assertFalse(b.challenge_pass_authorized)

    def test_03_two_traders_have_isolated_virtual_pnl(self):
        out=run(event(1),event(1,2,action="CLOSE",price="3002"),event(2),
                event(2,2,action="CLOSE",price="2997"),
                provisioned=(provision(1),provision(2)))
        self.assertEqual(out.distinct_traders,2)
        self.assertEqual(out.distinct_challenges,2)
        self.assertEqual(out.challenge_books[0].realized_net_after_all_fees_usd,Decimal("1.80"))
        self.assertEqual(out.challenge_books[1].realized_net_after_all_fees_usd,Decimal("-3.20"))
        self.assertEqual(out.company_real_broker_orders_emitted,0)

    def test_04_100_traders_do_not_create_100_broker_accounts(self):
        p=tuple(provision(i) for i in range(1,101))
        ev=tuple(z for i in range(1,101) for z in
                 (event(i),event(i,2,action="CLOSE",price="3001")))
        out=run(*ev,provisioned=p)
        self.assertEqual(out.distinct_traders,100)
        self.assertEqual(out.distinct_challenges,100)
        self.assertEqual(out.total_unique_events,200)
        self.assertEqual(out.company_real_broker_orders_emitted,0)

    def test_05_buy_position_profit_credits_only_own_book(self):
        b=run(event(),event(seq=2,action="CLOSE",price="3010")).challenge_books[0]
        self.assertEqual(b.closed_realized_gross_usd,Decimal("10"))
        self.assertEqual(b.realized_net_after_all_fees_usd,Decimal("9.80"))

    def test_06_sell_short_profit_uses_reversed_price_change(self):
        b=run(event(direction="SELL"),
              event(seq=2,action="CLOSE",direction="SELL",price="2998")).challenge_books[0]
        self.assertEqual(b.closed_realized_gross_usd,Decimal("2"))

    def test_07_open_venue_fee_is_counted_once(self):
        b=run(event()).challenge_books[0]
        self.assertEqual(b.total_fees_usd,Decimal("0.10"))
        self.assertEqual(b.cash_balance_excluding_unrealized_usd,Decimal("99.90"))

    def test_08_partial_close_does_not_count_as_fully_closed(self):
        b=run(event(qty="2"),
              event(seq=2,action="CLOSE",qty="1",price="3002")).challenge_books[0]
        self.assertEqual(b.fully_closed_positions_total,0)
        self.assertEqual(b.open_positions[0].remaining_ounces,Decimal("1"))
        self.assertEqual(b.realized_net_after_all_fees_usd,Decimal("1.80"))

    def test_09_final_partial_close_counts_one_not_two_positions(self):
        b=run(event(qty="2"),
              event(seq=2,action="CLOSE",qty="1",price="3002"),
              event(seq=3,action="CLOSE",qty="1",price="3003")).challenge_books[0]
        self.assertEqual(b.fully_closed_positions_total,1)
        self.assertEqual(b.open_positions,())
        self.assertEqual(b.closed_realized_gross_usd,Decimal("5"))

    def test_10_weighted_open_additions_keep_correct_cost_basis(self):
        b=run(event(qty="1",price="3000"),
              event(seq=2,action="OPEN",qty="1",price="3004"),
              event(seq=3,action="CLOSE",qty="2",price="3005")).challenge_books[0]
        self.assertEqual(b.closed_realized_gross_usd,Decimal("6"))
        self.assertEqual(b.fully_closed_positions_total,1)

    def test_11_close_without_open_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(action="CLOSE"))

    def test_12_overclose_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(),event(seq=2,action="CLOSE",qty="2"))

    def test_13_close_wrong_direction_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(),event(seq=2,action="CLOSE",direction="SELL"))

    def test_14_close_wrong_stage_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(),event(seq=2,action="CLOSE",stage=2),
                provisioned=(provision(max_unlocked_stage=2),))

    def test_15_completed_position_reference_cannot_reopen(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(),event(seq=2,action="CLOSE",price="3002"),
                event(seq=3,action="OPEN"))

    def test_16_stage_two_requires_server_unlocked_stage(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(stage=2))

    def test_17_two_stages_count_fully_closed_positions_separately(self):
        e=(event(),event(seq=2,action="CLOSE",price="3002"),
           event(seq=3,action="OPEN",stage=2,position="P-2"),
           event(seq=4,action="CLOSE",stage=2,position="P-2",price="3004"))
        b=run(*e,provisioned=(provision(max_unlocked_stage=2),)).challenge_books[0]
        self.assertEqual(b.fully_closed_positions_total,2)
        self.assertEqual(b.fully_closed_positions_stage_one,1)
        self.assertEqual(b.fully_closed_positions_stage_two,1)
        self.assertFalse(b.challenge_pass_authorized)

    def test_18_forged_cross_tenant_ledger_event_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(trader_ref="TRADER-2"))

    def test_19_unprovisioned_challenge_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(2))

    def test_20_same_challenge_ref_cannot_appear_twice_in_registry(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(provisioned=(provision(),provision(2,challenge_ref="CHALLENGE-1")))

    def test_21_wrong_contract_sha_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(provisioned=(provision(terms_sha256="b"*64),))

    def test_22_wrong_data_feed_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(feed_source="OTHER-SOURCE"))

    def test_23_event_id_collision_across_tenants_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(1),event(2,event_id="EVENT-1-1"),
                provisioned=(provision(1),provision(2)))

    def test_24_same_global_event_exact_replay_is_idempotent(self):
        e=event()
        b=run(e,e).challenge_books[0]
        self.assertEqual(b.unique_event_count,1)
        self.assertEqual(b.idempotent_duplicate_count,1)
        self.assertEqual(b.total_fees_usd,Decimal("0.10"))

    def test_25_same_event_id_modified_price_is_rejected(self):
        e=event()
        with self.assertRaises(VirtualLedgerRejected):
            run(e,replace(e,price_usd_per_ounce="3001"))

    def test_26_sequence_reuse_with_different_event_id_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(),event(seq=1,event_id="DIFFERENT-EVENT"))

    def test_27_sequence_gap_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(),event(seq=3,action="CLOSE"))

    def test_28_sequence_order_can_arrive_unsorted_but_is_replayed_by_sequence(self):
        a=run(event(),event(seq=2,action="CLOSE",price="3002"))
        b=run(event(seq=2,action="CLOSE",price="3002"),event())
        self.assertEqual(a.challenge_books[0].canonical_event_history_sha256,
                         b.challenge_books[0].canonical_event_history_sha256)

    def test_29_backwards_timestamp_relative_to_sequence_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(),event(seq=2,action="CLOSE",executed_at_utc=START))

    def test_30_timezone_naive_event_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(executed_at_utc=START.replace(tzinfo=None)))

    def test_31_future_virtual_execution_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(executed_at_utc=NOW+timedelta(seconds=1)))

    def test_32_end_boundary_of_28_day_window_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(executed_at_utc=START+timedelta(days=28)),
                server_now=START+timedelta(days=30))

    def test_33_qty_float_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(quantity_ounces=0.2))

    def test_34_nonfinite_price_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(price_usd_per_ounce="Infinity"))

    def test_35_negative_fee_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(fee_usd="-1"))

    def test_36_wrong_symbol_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(symbol="EURUSD"))

    def test_37_missing_evidence_digest_rejected(self):
        with self.assertRaises(VirtualLedgerRejected):
            run(event(raw_event_sha256=""))

    def test_38_shaped_evidence_hash_does_not_prove_actual_source(self):
        b=run(event()).challenge_books[0]
        self.assertFalse(b.externally_authenticated_simulator_feed)
        self.assertFalse(b.independently_verified_live_quotes)

    def test_39_event_digest_changes_when_fee_changes(self):
        a=run(event()).challenge_books[0]
        b=run(event(fee_usd="0.20")).challenge_books[0]
        self.assertNotEqual(a.canonical_event_history_sha256,b.canonical_event_history_sha256)

    def test_40_replay_duplicate_does_not_change_history_digest(self):
        e=event()
        a=run(e).challenge_books[0]
        b=run(e,e).challenge_books[0]
        self.assertEqual(a.canonical_event_history_sha256,b.canonical_event_history_sha256)

    def test_41_outputs_immutable_against_fake_execution_approval(self):
        b=run(event()).challenge_books[0]
        with self.assertRaises(FrozenInstanceError):
            b.broker_orders_authorized=True

    def test_42_cash_balance_explicitly_excludes_floating_equity(self):
        b=run(event()).challenge_books[0]
        self.assertFalse(b.floating_equity_and_risk_verified)
        self.assertEqual(len(b.open_positions),1)

    def test_43_stage_one_50_positions_not_automatically_a_passing_challenge(self):
        ev=tuple(
            e for i in range(1,51)
            for e in (
                event(seq=2*i-1,position=f"P-{i}"),
                event(seq=2*i,action="CLOSE",position=f"P-{i}",price="3001"),
            )
        )
        b=run(*ev).challenge_books[0]
        self.assertEqual(b.fully_closed_positions_total,50)
        self.assertFalse(b.challenge_pass_authorized)

    def test_44_duplicate_source_events_cannot_create_extra_fifty_closes(self):
        e=(event(),event(seq=2,action="CLOSE",price="3001"))
        b=run(*e,*e).challenge_books[0]
        self.assertEqual(b.fully_closed_positions_total,1)
        self.assertEqual(b.idempotent_duplicate_count,2)

    def test_45_multi_tenant_ledger_has_no_real_broker_orders(self):
        out=run(event(1),event(2),provisioned=(provision(1),provision(2)))
        self.assertEqual(out.company_real_broker_orders_emitted,0)
        self.assertFalse(out.commercial_service_enabled)


    def test_46_equal_decimals_have_same_audit_hash_after_database_reload(self):
        plain=run(event(),event(seq=2,action="CLOSE",price="3002"))
        persisted=run(
            event(qty="1.0000",price="3000.0000",fee_usd="0.1000"),
            event(seq=2,action="CLOSE",price="3002.0000",
                  qty="1.0000",fee_usd="0.1000"),
        )
        self.assertEqual(plain.challenge_books[0].canonical_event_history_sha256,
                         persisted.challenge_books[0].canonical_event_history_sha256)

    def test_47_fifo_uses_oldest_open_lot_on_partial_close(self):
        book=run(
            event(price="3000",qty="1"),
            event(seq=2,action="OPEN",price="3003",qty="2"),
            event(seq=3,action="CLOSE",price="3004",qty="1"),
        ).challenge_books[0]
        self.assertEqual(book.closed_realized_gross_usd,Decimal("4"))
        self.assertEqual(book.open_positions[0].remaining_ounces,Decimal("2"))
        self.assertEqual(book.open_positions[0].weighted_open_price_usd,Decimal("3003"))

    def test_48_exact_eight_decimal_usd_profit_retained(self):
        book=run(
            event(qty="0.0001",price="3000.0001",fee_usd="0"),
            event(seq=2,action="CLOSE",qty="0.0001",
                  price="3000.0002",fee_usd="0"),
        ).challenge_books[0]
        self.assertEqual(book.realized_net_after_all_fees_usd,
                         Decimal("0.00000001"))
        self.assertEqual(book.cash_balance_excluding_unrealized_usd,
                         Decimal("100.00000001"))

    def test_49_fifo_multiple_partial_closures_preserve_exact_total(self):
        book=run(
            event(qty="1",price="3000",fee_usd="0"),
            event(seq=2,action="OPEN",qty="1",price="3002",fee_usd="0"),
            event(seq=3,action="CLOSE",qty="0.5000",price="3004",fee_usd="0"),
            event(seq=4,action="CLOSE",qty="1.5000",price="3005",fee_usd="0"),
        ).challenge_books[0]
        self.assertEqual(book.closed_realized_gross_usd,Decimal("7.5"))
        self.assertEqual(book.fully_closed_positions_total,1)

    def test_50_ledger_is_not_a_broker_trade_and_has_no_paid_entitlements(self):
        book=run(event(),event(seq=2,action="CLOSE",price="3002")).challenge_books[0]
        self.assertFalse(book.paid_enrollment_authorized)
        self.assertFalse(book.broker_orders_authorized)
        self.assertFalse(book.payouts_authorized)
        self.assertFalse(book.floating_equity_and_risk_verified)

    def test_51_closed_positions_do_not_count_raw_fills(self):
        book=run(event(),event(seq=2,action="OPEN",price="3001"),
                 event(seq=3,action="CLOSE",qty="1",price="3002"),
                 event(seq=4,action="CLOSE",qty="1",price="3003")).challenge_books[0]
        self.assertEqual(book.unique_event_count,4)
        self.assertEqual(book.fully_closed_positions_total,1)


if __name__=="__main__":
    unittest.main()
