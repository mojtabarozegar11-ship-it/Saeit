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
