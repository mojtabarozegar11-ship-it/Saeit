import hashlib
import unittest
from datetime import datetime, timezone
from decimal import Decimal

try:
    from mojtaba_signal_order_ledger import (
        PendingSignalOrderLedger,
        SignalLedgerError,
    )
    from mojtaba_signal_order_contract import (
        SignalOrderContractError,
        SignalOrderIntent,
    )
    from mojtaba_signal_service_contract import (
        BOT_IDENTITY,
        SignalOffer,
        SignalServiceKind,
        SignalTenantRoute,
    )
except ModuleNotFoundError:
    from core.mojtaba_signal_order_ledger import (
        PendingSignalOrderLedger,
        SignalLedgerError,
    )
    from core.mojtaba_signal_order_contract import (
        SignalOrderContractError,
        SignalOrderIntent,
    )
    from core.mojtaba_signal_service_contract import (
        BOT_IDENTITY,
        SignalOffer,
        SignalServiceKind,
        SignalTenantRoute,
    )


NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


class PendingSignalOrderLedgerTests(unittest.TestCase):
    def route(self, **changes):
        values = {
            "tenant_id": "mojplaywin",
            "canonical_host": "mojplaywin.com",
            "path_prefix": "/signals/",
            "language": "en",
            "owner_approved": True,
            "legal_reviewed": True,
            "active": True,
        }
        values.update(changes)
        return SignalTenantRoute(**values)

    def offer(self, **changes):
        values = {
            "offer_id": "research-001",
            "tenant_id": "mojplaywin",
            "bot_identity": BOT_IDENTITY,
            "language": "en",
            "service_kind": SignalServiceKind.RESEARCH_SUMMARY,
            "price": Decimal("10"),
            "currency": "TRX",
            "owner_approved": True,
            "legal_reviewed": True,
            "rights_cleared": True,
            "active": True,
        }
        values.update(changes)
        return SignalOffer(**values)

    def intent(self, **changes):
        values = {
            "order_id": "order-001",
            "tenant_id": "mojplaywin",
            "offer_id": "research-001",
            "bot_identity": BOT_IDENTITY,
            "language": "en",
            "price": Decimal("10"),
            "currency": "TRX",
            "customer_ref_digest": hashlib.sha256(
                b"customer-reference"
            ).hexdigest(),
            "requested_at": "2026-11-15T11:59:00Z",
        }
        values.update(changes)
        return SignalOrderIntent(**values)

    def test_create_is_pending_and_non_financial(self):
        ledger = PendingSignalOrderLedger()
        receipt = ledger.record(
            self.intent(), self.route(), self.offer(), now=NOW
        )
        self.assertTrue(receipt.created)
        self.assertEqual(receipt.record["state"], "awaiting_external_settlement")
        self.assertTrue(receipt.record["payment_required"])
        self.assertFalse(receipt.record["entitlement_granted"])
        self.assertFalse(receipt.record["settlement_verified"])
        self.assertFalse(receipt.record["financial_signal"])
        self.assertEqual(len(ledger), 1)

    def test_same_intent_replays_idempotently(self):
        ledger = PendingSignalOrderLedger()
        first = ledger.record(self.intent(), self.route(), self.offer(), now=NOW)
        second = ledger.record(self.intent(), self.route(), self.offer(), now=NOW)
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.record, second.record)
        self.assertEqual(len(ledger), 1)

    def test_conflicting_reuse_of_order_id_is_rejected(self):
        ledger = PendingSignalOrderLedger()
        ledger.record(self.intent(), self.route(), self.offer(), now=NOW)
        conflicting = self.intent(
            customer_ref_digest=hashlib.sha256(b"different").hexdigest()
        )
        with self.assertRaisesRegex(SignalLedgerError, "order_id_conflict"):
            ledger.record(conflicting, self.route(), self.offer(), now=NOW)
        self.assertEqual(len(ledger), 1)

    def test_receipt_and_get_are_copy_isolated(self):
        ledger = PendingSignalOrderLedger()
        receipt = ledger.record(self.intent(), self.route(), self.offer(), now=NOW)
        receipt.record["state"] = "paid"
        stored = ledger.get("order-001")
        self.assertEqual(stored["state"], "awaiting_external_settlement")

    def test_snapshot_is_deterministic(self):
        ledger = PendingSignalOrderLedger()
        ledger.record(
            self.intent(order_id="order-z"), self.route(), self.offer(), now=NOW
        )
        ledger.record(
            self.intent(order_id="order-a"), self.route(), self.offer(), now=NOW
        )
        self.assertEqual(
            [row["order_id"] for row in ledger.snapshot()],
            ["order-a", "order-z"],
        )

    def test_unknown_order_is_not_a_success(self):
        ledger = PendingSignalOrderLedger()
        self.assertIsNone(ledger.get("missing-order"))

    def test_invalid_order_id_is_rejected(self):
        with self.assertRaisesRegex(SignalLedgerError, "order_id_required"):
            PendingSignalOrderLedger().get("")

    def test_invalid_contract_never_writes(self):
        ledger = PendingSignalOrderLedger()
        with self.assertRaises(SignalOrderContractError):
            ledger.record(
                self.intent(), self.route(active=False), self.offer(), now=NOW
            )
        self.assertEqual(len(ledger), 0)

    def test_raw_customer_identifier_is_not_stored(self):
        ledger = PendingSignalOrderLedger()
        receipt = ledger.record(
            self.intent(), self.route(), self.offer(), now=NOW
        )
        self.assertNotIn("customer-reference", str(receipt.record))
        self.assertNotIn("email", str(receipt.record))

    def test_ledger_capacity_configuration_is_bounded(self):
        for cap in (0, -1, True, 100001, "100"):
            with self.subTest(cap=cap), self.assertRaisesRegex(SignalLedgerError, "capacity_invalid"):
                PendingSignalOrderLedger(max_records=cap)

    def test_one_pending_order_fills_capacity(self):
        ledger = PendingSignalOrderLedger(max_records=1)
        ledger.record(self.intent(), self.route(), self.offer(), now=NOW)
        with self.assertRaisesRegex(SignalLedgerError, "capacity_reached"):
            ledger.record(self.intent(order_id="order-002"), self.route(), self.offer(), now=NOW)
        self.assertEqual(len(ledger), 1)

    def test_idempotent_retry_works_at_capacity(self):
        ledger = PendingSignalOrderLedger(max_records=1)
        ledger.record(self.intent(), self.route(), self.offer(), now=NOW)
        self.assertFalse(ledger.record(self.intent(), self.route(), self.offer(), now=NOW).created)

    def test_atomic_two_order_batch_inserts_both(self):
        ledger = PendingSignalOrderLedger()
        rows = [
            (self.intent(order_id="order-001"), self.route(), self.offer()),
            (self.intent(order_id="order-002"), self.route(), self.offer()),
        ]
        results = ledger.record_batch(rows, now=NOW)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.created for result in results))
        self.assertEqual(len(ledger), 2)

    def test_atomic_batch_retry_is_idempotent(self):
        ledger = PendingSignalOrderLedger()
        rows = [(self.intent(order_id="order-001"), self.route(), self.offer())]
        ledger.record_batch(rows, now=NOW)
        self.assertFalse(ledger.record_batch(rows, now=NOW)[0].created)

    def test_invalid_batch_does_not_leave_partially_created_orders(self):
        ledger = PendingSignalOrderLedger()
        rows = [
            (self.intent(order_id="order-001"), self.route(), self.offer()),
            (self.intent(order_id="order-002"), self.route(active=False), self.offer()),
        ]
        with self.assertRaises(SignalOrderContractError):
            ledger.record_batch(rows, now=NOW)
        self.assertEqual(len(ledger), 0)

    def test_batch_conflict_is_atomic_for_all_orders(self):
        ledger = PendingSignalOrderLedger()
        ledger.record(self.intent(order_id="order-002"), self.route(), self.offer(), now=NOW)
        rows = [
            (self.intent(order_id="order-001"), self.route(), self.offer()),
            (self.intent(order_id="order-002", price=Decimal("9")), self.route(), self.offer()),
        ]
        with self.assertRaises(SignalOrderContractError):
            ledger.record_batch(rows, now=NOW)
        self.assertIsNone(ledger.get("order-001"))
        self.assertEqual(len(ledger), 1)

    def test_batch_capacity_overflow_rolls_back_all(self):
        ledger = PendingSignalOrderLedger(max_records=1)
        rows = [
            (self.intent(order_id="order-001"), self.route(), self.offer()),
            (self.intent(order_id="order-002"), self.route(), self.offer()),
        ]
        with self.assertRaisesRegex(SignalLedgerError, "capacity_reached"):
            ledger.record_batch(rows, now=NOW)
        self.assertEqual(len(ledger), 0)

    def test_duplicate_order_in_single_batch_is_rejected(self):
        ledger = PendingSignalOrderLedger()
        row = (self.intent(), self.route(), self.offer())
        with self.assertRaisesRegex(SignalLedgerError, "duplicate_order_id_in_batch"):
            ledger.record_batch([row, row], now=NOW)
        self.assertEqual(len(ledger), 0)

    def test_batch_requires_expected_container_and_row_shape(self):
        ledger = PendingSignalOrderLedger()
        for invalid in (None, {}, "one-order"):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(SignalLedgerError, "order_batch_required"):
                ledger.record_batch(invalid, now=NOW)
        with self.assertRaisesRegex(SignalLedgerError, "order_batch_row_invalid"):
            ledger.record_batch([(self.intent(), self.route())], now=NOW)

    def test_batch_oversize_fails_before_side_effects(self):
        ledger = PendingSignalOrderLedger()
        row = (self.intent(), self.route(), self.offer())
        with self.assertRaisesRegex(SignalLedgerError, "order_batch_too_large"):
            ledger.record_batch([row] * 501, now=NOW)
        self.assertEqual(len(ledger), 0)

    def test_empty_batch_is_harmless(self):
        ledger = PendingSignalOrderLedger()
        self.assertEqual(ledger.record_batch([], now=NOW), ())

    def test_get_refuses_unbounded_or_malformed_ids(self):
        ledger = PendingSignalOrderLedger()
        for bad in ("a", "x" * 10000, "../secret", "ORDER-001", None, 12):
            with self.subTest(bad=str(bad)[:20]), self.assertRaisesRegex(SignalLedgerError, "order_id_required"):
                ledger.get(bad)

    def test_snapshot_mutation_does_not_change_stored_order(self):
        ledger = PendingSignalOrderLedger()
        ledger.record(self.intent(), self.route(), self.offer(), now=NOW)
        ledger.snapshot()[0]["entitlement_granted"] = True
        self.assertFalse(ledger.get("order-001")["entitlement_granted"])

    def test_concurrent_idempotent_writers_create_exactly_one_order(self):
        from concurrent.futures import ThreadPoolExecutor
        ledger = PendingSignalOrderLedger(max_records=1)
        def worker(_):
            return ledger.record(self.intent(), self.route(), self.offer(), now=NOW).created
        with ThreadPoolExecutor(max_workers=8) as pool:
            created = list(pool.map(worker, range(32)))
        self.assertEqual(sum(created), 1)
        self.assertEqual(len(ledger), 1)

    def test_concurrent_distinct_orders_cannot_exceed_capacity(self):
        from concurrent.futures import ThreadPoolExecutor
        ledger = PendingSignalOrderLedger(max_records=3)
        def worker(i):
            try:
                ledger.record(self.intent(order_id="order-%04d" % i), self.route(), self.offer(), now=NOW)
                return True
            except SignalLedgerError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            success = list(pool.map(worker, range(24)))
        self.assertEqual(sum(success), 3)
        self.assertEqual(len(ledger), 3)
