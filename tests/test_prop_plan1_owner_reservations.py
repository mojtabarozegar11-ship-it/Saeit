"""Tests for the durable owner reservation and order attribution ledger."""
from decimal import Decimal as D
import os
import tempfile
import threading
import unittest

from prop_firm.plan1_owner_reservations import (
    InvalidTransition, LedgerConflict, ReservationLedger, UnknownReservation,
)


class ReservationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(prefix="mojprop-ledger-", delete=False)
        self.tmp.close()
        self.ledger = ReservationLedger(self.tmp.name)

    def tearDown(self):
        self.ledger.close()
        os.unlink(self.tmp.name)

    def reserve(self, **changes):
        values = dict(
            reservation_id="RES-001",
            idempotency_key="IDEM-001",
            account_ref="OWNER-LIVE",
            trader_ref="TRADER-A",
            capital_usd=D("100"),
            risk_usd=D("0.80"),
            margin_usd=D("10"),
            max_account_risk_usd=D("1.60"),
            max_trader_risk_usd=D("1.60"),
            max_account_capital_usd=D("100"),
            order_ref="ORDER-001",
        )
        values.update(changes)
        return self.ledger.reserve(**values)

    def test_schema_is_created_and_empty_exposure_is_zero(self):
        e = self.ledger.exposure("OWNER-LIVE")
        self.assertEqual(e.reserved_capital_usd, D("0"))
        self.assertEqual(e.reserved_risk_usd, D("0"))
        self.assertEqual(e.reservation_count, 0)

    def test_reserve_binds_account_and_trader(self):
        r = self.reserve()
        self.assertEqual(r.status, "reserved")
        self.assertEqual(r.account_ref, "OWNER-LIVE")
        self.assertEqual(r.trader_ref, "TRADER-A")
        self.assertEqual(r.risk_usd, D("0.80"))

    def test_idempotent_retry_returns_same_entry(self):
        first = self.reserve()
        second = self.reserve()
        self.assertEqual(first, second)
        self.assertEqual(self.ledger.exposure("OWNER-LIVE").reservation_count, 1)

    def test_idempotency_reuse_with_changed_risk_is_rejected(self):
        self.reserve()
        with self.assertRaises(LedgerConflict):
            self.reserve(risk_usd=D("0.81"))

    def test_duplicate_reservation_id_is_rejected(self):
        self.reserve()
        with self.assertRaises(LedgerConflict):
            self.reserve(idempotency_key="IDEM-002")

    def test_account_risk_limit_is_atomic(self):
        self.reserve()
        with self.assertRaises(LedgerConflict):
            self.reserve(
                reservation_id="RES-002", idempotency_key="IDEM-002",
                trader_ref="TRADER-B", order_ref="ORDER-002",
            )

    def test_trader_risk_limit_is_separate(self):
        self.reserve()
        with self.assertRaises(LedgerConflict):
            self.reserve(
                reservation_id="RES-002", idempotency_key="IDEM-002",
                order_ref="ORDER-002", max_account_risk_usd=D("3.2"),
            )

    def test_capital_limit_is_enforced(self):
        with self.assertRaises(LedgerConflict):
            self.reserve(capital_usd=D("100.01"), max_account_capital_usd=D("100"))

    def test_other_account_does_not_consume_this_limit(self):
        self.reserve()
        r = self.reserve(
            reservation_id="RES-002", idempotency_key="IDEM-002",
            account_ref="OWNER-OTHER", order_ref="ORDER-002",
        )
        self.assertEqual(r.account_ref, "OWNER-OTHER")

    def test_trader_exposure_isolated_in_query(self):
        self.reserve()
        self.reserve(
            reservation_id="RES-002", idempotency_key="IDEM-002",
            trader_ref="TRADER-B", order_ref="ORDER-002",
            max_account_risk_usd=D("3.2"),
        )
        self.assertEqual(
            self.ledger.exposure("OWNER-LIVE", "TRADER-A").reserved_risk_usd,
            D("0.80"),
        )
        self.assertEqual(
            self.ledger.exposure("OWNER-LIVE", "TRADER-B").reserved_risk_usd,
            D("0.80"),
        )

    def test_broker_order_binding_is_definitive(self):
        self.reserve()
        r = self.ledger.bind_broker_order(
            reservation_id="RES-001", broker_order_ref="BROKER-001"
        )
        self.assertEqual(r.status, "submitted")
        self.assertEqual(r.broker_order_ref, "BROKER-001")
        self.assertEqual(self.ledger.exposure("OWNER-LIVE").reservation_count, 1)

    def test_binding_is_idempotent_for_same_order(self):
        self.reserve()
        first = self.ledger.bind_broker_order(
            reservation_id="RES-001", broker_order_ref="BROKER-001"
        )
        second = self.ledger.bind_broker_order(
            reservation_id="RES-001", broker_order_ref="BROKER-001"
        )
        self.assertEqual(first, second)

    def test_one_reservation_cannot_bind_two_orders(self):
        self.reserve()
        self.ledger.bind_broker_order(
            reservation_id="RES-001", broker_order_ref="BROKER-001"
        )
        with self.assertRaises(LedgerConflict):
            self.ledger.bind_broker_order(
                reservation_id="RES-001", broker_order_ref="BROKER-002"
            )

    def test_one_broker_order_cannot_bind_two_traders(self):
        self.reserve()
        self.reserve(
            reservation_id="RES-002", idempotency_key="IDEM-002",
            trader_ref="TRADER-B", order_ref="ORDER-002",
            max_account_risk_usd=D("3.2"),
        )
        self.ledger.bind_broker_order(
            reservation_id="RES-001", broker_order_ref="BROKER-001"
        )
        with self.assertRaises(LedgerConflict):
            self.ledger.bind_broker_order(
                reservation_id="RES-002", broker_order_ref="BROKER-001"
            )

    def test_submitted_entry_cannot_be_released_directly(self):
        self.reserve()
        self.ledger.bind_broker_order(
            reservation_id="RES-001", broker_order_ref="BROKER-001"
        )
        with self.assertRaises(InvalidTransition):
            self.ledger.release(reservation_id="RES-001", reason="uncertain")

    def test_reserved_entry_can_be_released(self):
        self.reserve()
        r = self.ledger.release(reservation_id="RES-001", reason="broker timeout")
        self.assertEqual(r.status, "released")
        self.assertEqual(self.ledger.exposure("OWNER-LIVE").reservation_count, 0)

    def test_release_is_idempotent(self):
        self.reserve()
        first = self.ledger.release(reservation_id="RES-001", reason="cancelled")
        second = self.ledger.release(reservation_id="RES-001", reason="different")
        self.assertEqual(first, second)

    def test_released_capital_can_be_reserved_again(self):
        self.reserve()
        self.ledger.release(reservation_id="RES-001", reason="not submitted")
        r = self.reserve(
            reservation_id="RES-002", idempotency_key="IDEM-002",
            order_ref="ORDER-002",
        )
        self.assertEqual(r.status, "reserved")

    def test_only_submitted_entry_can_settle(self):
        self.reserve()
        with self.assertRaises(InvalidTransition):
            self.ledger.settle(reservation_id="RES-001", outcome="profit")

    def test_settlement_releases_active_exposure(self):
        self.reserve()
        self.ledger.bind_broker_order(
            reservation_id="RES-001", broker_order_ref="BROKER-001"
        )
        r = self.ledger.settle(reservation_id="RES-001", outcome="closed")
        self.assertEqual(r.status, "settled")
        self.assertEqual(self.ledger.exposure("OWNER-LIVE").reservation_count, 0)

    def test_settlement_is_idempotent(self):
        self.reserve()
        self.ledger.bind_broker_order(
            reservation_id="RES-001", broker_order_ref="BROKER-001"
        )
        first = self.ledger.settle(reservation_id="RES-001", outcome="closed")
        second = self.ledger.settle(reservation_id="RES-001", outcome="changed")
        self.assertEqual(first, second)

    def test_unknown_reservation_is_rejected(self):
        with self.assertRaises(UnknownReservation):
            self.ledger.get("RES-404")

    def test_invalid_money_and_reference_are_rejected(self):
        with self.assertRaises(ValueError):
            self.reserve(risk_usd=D("0"))
        with self.assertRaises(ValueError):
            self.reserve(trader_ref="not valid")
        with self.assertRaises(ValueError):
            self.reserve(capital_usd=D("0.000000001"))

    def test_event_chain_is_valid_after_transitions(self):
        self.reserve()
        self.ledger.bind_broker_order(
            reservation_id="RES-001", broker_order_ref="BROKER-001"
        )
        self.ledger.settle(reservation_id="RES-001", outcome="closed")
        self.assertTrue(self.ledger.verify_event_chain())

    def test_failed_transition_does_not_add_event(self):
        self.reserve()
        before = self.ledger._db.execute(
            "SELECT COUNT(*) AS n FROM reservation_events"
        ).fetchone()["n"]
        with self.assertRaises(InvalidTransition):
            self.ledger.settle(reservation_id="RES-001", outcome="too early")
        after = self.ledger._db.execute(
            "SELECT COUNT(*) AS n FROM reservation_events"
        ).fetchone()["n"]
        self.assertEqual(before, after)

    def test_concurrent_reservations_cannot_breach_account_limit(self):
        paths = [self.tmp.name, self.tmp.name]
        barrier = threading.Barrier(2)
        outcomes = []

        def worker(index):
            with ReservationLedger(paths[index]) as ledger:
                barrier.wait()
                try:
                    ledger.reserve(
                        reservation_id=f"RES-{index+10}",
                        idempotency_key=f"IDEM-{index+10}",
                        account_ref="OWNER-LIVE",
                        trader_ref=f"TRADER-{index+10}",
                        capital_usd=D("100"),
                        risk_usd=D("0.80"),
                        margin_usd=D("10"),
                        max_account_risk_usd=D("0.80"),
                        max_trader_risk_usd=D("0.80"),
                        max_account_capital_usd=D("200"),
                        order_ref=f"ORDER-{index+10}",
                    )
                    outcomes.append("accepted")
                except LedgerConflict:
                    outcomes.append("rejected")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(outcomes), ["accepted", "rejected"])
        self.assertEqual(
            self.ledger.exposure("OWNER-LIVE").reserved_risk_usd, D("0.80")
        )


if __name__ == "__main__":
    unittest.main()
