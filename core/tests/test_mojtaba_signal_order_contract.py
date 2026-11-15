import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib

try:
    from mojtaba_signal_order_contract import (
        SignalOrderContractError, SignalOrderIntent,
        build_pending_order_record, validate_order_batch,
        validate_order_intent,
    )
    from mojtaba_signal_service_contract import (
        BOT_IDENTITY, SignalOffer, SignalServiceKind, SignalTenantRoute,
    )
except ModuleNotFoundError:
    from core.mojtaba_signal_order_contract import (
        SignalOrderContractError, SignalOrderIntent,
        build_pending_order_record, validate_order_batch,
        validate_order_intent,
    )
    from core.mojtaba_signal_service_contract import (
        BOT_IDENTITY, SignalOffer, SignalServiceKind, SignalTenantRoute,
    )


NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


class SignalOrderContractTests(unittest.TestCase):
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

    def test_valid_intent_builds_pending_record(self):
        record = build_pending_order_record(
            self.intent(), self.route(), self.offer(), now=NOW
        )
        self.assertEqual(record["state"], "awaiting_external_settlement")
        self.assertTrue(record["payment_required"])
        self.assertFalse(record["entitlement_granted"])
        self.assertFalse(record["financial_signal"])

    def test_route_must_be_active(self):
        with self.assertRaisesRegex(SignalOrderContractError, "route_not_active"):
            validate_order_intent(
                self.intent(), self.route(active=False), self.offer(), now=NOW
            )

    def test_offer_must_be_active(self):
        with self.assertRaisesRegex(SignalOrderContractError, "offer_not_active"):
            validate_order_intent(
                self.intent(), self.route(), self.offer(active=False), now=NOW
            )

    def test_tenant_mismatch_is_rejected(self):
        with self.assertRaisesRegex(SignalOrderContractError, "order_tenant_mismatch"):
            validate_order_intent(
                self.intent(tenant_id="other"), self.route(), self.offer(), now=NOW
            )

    def test_offer_mismatch_is_rejected(self):
        with self.assertRaisesRegex(SignalOrderContractError, "order_offer_mismatch"):
            validate_order_intent(
                self.intent(offer_id="other-offer"), self.route(), self.offer(), now=NOW
            )

    def test_price_and_currency_must_match_offer(self):
        with self.assertRaisesRegex(SignalOrderContractError, "order_price_mismatch"):
            validate_order_intent(
                self.intent(price=Decimal("11")), self.route(), self.offer(), now=NOW
            )
        with self.assertRaisesRegex(SignalOrderContractError, "order_currency_mismatch"):
            validate_order_intent(
                self.intent(currency="USD"), self.route(), self.offer(), now=NOW
            )

    def test_paid_state_cannot_be_supplied_by_customer(self):
        with self.assertRaisesRegex(SignalOrderContractError, "settlement_required"):
            validate_order_intent(
                self.intent(state="paid"), self.route(), self.offer(), now=NOW
            )

    def test_future_order_is_rejected(self):
        with self.assertRaisesRegex(SignalOrderContractError, "order_requested_in_future"):
            validate_order_intent(
                self.intent(requested_at="2026-11-15T12:01:00Z"),
                self.route(), self.offer(), now=NOW
            )

    def test_customer_reference_must_be_digest(self):
        with self.assertRaisesRegex(SignalOrderContractError, "customer_ref_digest_invalid"):
            validate_order_intent(
                self.intent(customer_ref_digest="email@example.com"),
                self.route(), self.offer(), now=NOW
            )

    def test_wrong_identity_is_rejected(self):
        with self.assertRaisesRegex(SignalOrderContractError, "independent_bot_identity"):
            validate_order_intent(
                self.intent(bot_identity="other.bot.ai"),
                self.route(), self.offer(), now=NOW
            )

    def test_batch_rejects_duplicate_ids(self):
        with self.assertRaisesRegex(SignalOrderContractError, "duplicate_order_id"):
            validate_order_batch([self.intent(), self.intent()])

    def test_batch_accepts_distinct_ids(self):
        result = validate_order_batch([
            self.intent(order_id="order-001"),
            self.intent(order_id="order-002"),
        ])
        self.assertEqual(len(result), 2)

    def test_batch_requires_list_or_tuple(self):
        with self.assertRaisesRegex(SignalOrderContractError, "order_batch_required"):
            validate_order_batch({"order-001": self.intent()})

    def test_no_raw_customer_identifier_is_returned(self):
        record = build_pending_order_record(
            self.intent(), self.route(), self.offer(), now=NOW
        )
        self.assertNotIn("email", str(record))
        self.assertEqual(len(record["customer_ref_digest"]), 64)


if __name__ == "__main__":
    unittest.main()
