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


    def test_customer_cannot_claim_external_pending_state(self):
        with self.assertRaisesRegex(SignalOrderContractError, "settlement_required"):
            validate_order_intent(
                self.intent(state="pending_external_settlement"),
                self.route(), self.offer(), now=NOW
            )

    def test_stale_order_requires_new_customer_intent(self):
        with self.assertRaisesRegex(SignalOrderContractError, "stale_order_intent"):
            validate_order_intent(
                self.intent(requested_at="2026-11-13T11:00:00Z"),
                self.route(), self.offer(), now=NOW
            )

    def test_non_datetime_server_clock_rejected(self):
        with self.assertRaisesRegex(SignalOrderContractError, "order_clock"):
            validate_order_intent(
                self.intent(), self.route(), self.offer(), now=object()
            )

    def test_placeholder_customer_hash_is_not_an_identity(self):
        with self.assertRaisesRegex(SignalOrderContractError, "customer_ref_digest"):
            validate_order_intent(
                self.intent(customer_ref_digest="0" * 64),
                self.route(), self.offer(), now=NOW
            )

    def test_trx_cannot_have_more_than_six_effective_decimals(self):
        price = Decimal("1.1234567")
        with self.assertRaisesRegex(SignalOrderContractError, "order_price_precision"):
            validate_order_intent(
                self.intent(price=price), self.route(),
                self.offer(price=price), now=NOW
            )

    def test_trx_trailing_zeroes_do_not_change_effective_precision(self):
        price = Decimal("1.23000000")
        validate_order_intent(
            self.intent(price=price), self.route(),
            self.offer(price=price), now=NOW
        )

    def test_usd_precision_limited_to_cents(self):
        price = Decimal("1.001")
        with self.assertRaisesRegex(SignalOrderContractError, "order_price_precision"):
            validate_order_intent(
                self.intent(price=price, currency="USD"), self.route(),
                self.offer(price=price, currency="USD"), now=NOW
            )

    def test_extreme_amounts_are_rejected_before_ledger(self):
        price = Decimal("1000000000")
        with self.assertRaisesRegex(SignalOrderContractError, "order_price_out_of_bounds"):
            validate_order_intent(
                self.intent(price=price), self.route(),
                self.offer(price=price), now=NOW
            )

    def test_malformed_batch_entry_reports_contract_error(self):
        with self.assertRaisesRegex(SignalOrderContractError, "order_intent_required"):
            validate_order_batch([None])

    def test_oversized_batch_is_bounded(self):
        with self.assertRaisesRegex(SignalOrderContractError, "order_batch_too_large"):
            validate_order_batch([self.intent()] * 501)

    def test_pending_record_tracks_host_and_does_not_imply_revenue(self):
        record = build_pending_order_record(
            self.intent(), self.route(), self.offer(), now=NOW
        )
        self.assertEqual(record["canonical_host"], "mojplaywin.com")
        self.assertEqual(record["path_prefix"], "/signals/")
        self.assertEqual(record["requested_at"], "2026-11-15T11:59:00Z")
        for key in ("entitlement_granted", "receipt_issued",
                    "delivery_verified", "settlement_verified"):
            self.assertIs(record[key], False)



if __name__ == "__main__":
    unittest.main()
