"""Regression suite for the offline, signed TRX invoice proposal contract."""
import base64
import hashlib
import hmac
import json
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

try:
    from core.mojtaba_signal_order_contract import SignalOrderIntent, build_pending_order_record
    from core.mojtaba_signal_service_contract import BOT_IDENTITY, SignalOffer, SignalServiceKind, SignalTenantRoute
    from core.mojtaba_signal_tron_invoice_contract import (
        TrxQuoteError, build_trx_invoice_quote, verify_trx_invoice_quote,
    )
except ModuleNotFoundError:
    from mojtaba_signal_order_contract import SignalOrderIntent, build_pending_order_record
    from mojtaba_signal_service_contract import BOT_IDENTITY, SignalOffer, SignalServiceKind, SignalTenantRoute
    from mojtaba_signal_tron_invoice_contract import (
        TrxQuoteError, build_trx_invoice_quote, verify_trx_invoice_quote,
    )


NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
SECRET = b"secure-test-only-quote-signing-key-" + b"x" * 32
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def valid_tron_address(byte=1):
    raw = bytes([0x41]) + bytes([byte]) * 20
    raw += hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
    n = int.from_bytes(raw, "big")
    result = ""
    while n:
        n, remainder = divmod(n, 58)
        result = ALPHABET[remainder] + result
    return "1" * (len(raw) - len(raw.lstrip(b"\x00"))) + result


class TrxSignalQuoteTests(unittest.TestCase):
    def setUp(self):
        self.receiver = valid_tron_address()
        self.route = SignalTenantRoute(
            tenant_id="mojplaywin", canonical_host="mojplaywin.com",
            path_prefix="/signals/", language="en", owner_approved=True,
            legal_reviewed=True, active=True,
        )
        self.offer = SignalOffer(
            offer_id="economic-report", tenant_id="mojplaywin",
            bot_identity=BOT_IDENTITY, language="en",
            service_kind=SignalServiceKind.ECONOMIC_REPORT,
            price=Decimal("12.345678"), currency="TRX",
            owner_approved=True, legal_reviewed=True,
            rights_cleared=True, active=True,
        )
        self.intent = SignalOrderIntent(
            order_id="order-0001", tenant_id="mojplaywin",
            offer_id="economic-report", bot_identity=BOT_IDENTITY,
            language="en", price=Decimal("12.345678"), currency="TRX",
            customer_ref_digest=hashlib.sha256(b"private-customer").hexdigest(),
            requested_at="2026-11-15T11:59:00Z",
        )
        self.pending = build_pending_order_record(self.intent, self.route, self.offer, now=NOW)

    def issue(self, **overrides):
        args = dict(
            pending_order=self.pending, route=self.route, offer=self.offer,
            invoice_id="invoice-0001", receiver_address=self.receiver,
            trusted_receiver_address=self.receiver,
            signing_secret=SECRET, now=NOW,
        )
        args.update(overrides)
        return build_trx_invoice_quote(**args)

    def verify(self, quote, **overrides):
        args = dict(
            token=quote.signed_token, pending_order=self.pending,
            route=self.route, offer=self.offer,
            trusted_receiver_address=self.receiver,
            signing_secret=SECRET, now=NOW,
        )
        args.update(overrides)
        return verify_trx_invoice_quote(**args)

    def resign(self, quote, **changes):
        first, _ = quote.signed_token.split(".")
        payload = json.loads(base64.urlsafe_b64decode(first + "=" * (-len(first) % 4)))
        payload.update(changes)
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        encoded = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
        signature = base64.urlsafe_b64encode(hmac.new(SECRET, raw, hashlib.sha256).digest()).rstrip(b"=").decode()
        return encoded + "." + signature

    def test_quote_is_pending_only(self):
        q = self.issue()
        self.assertEqual(q.amount_sun, 12345678)
        self.assertFalse(q.payment_collected)
        self.assertFalse(q.entitlement_granted)
        self.assertEqual(q.state, "pending_external_settlement")

    def test_signed_quote_round_trip(self):
        q = self.issue()
        claims = self.verify(q)
        self.assertEqual(claims["order_id"], self.intent.order_id)
        self.assertEqual(claims["receiver_address"], self.receiver)
        self.assertEqual(claims["network"], "tron-mainnet")

    def test_same_inputs_produce_same_immutable_quote(self):
        self.assertEqual(self.issue(), self.issue())

    def test_receiver_address_wrong_chain_prefix(self):
        with self.assertRaisesRegex(TrxQuoteError, "receiver_invalid"):
            self.issue(receiver_address="0x" + "0" * 40)

    def test_receiver_checksum_must_match(self):
        bad = self.receiver[:-1] + ("1" if self.receiver[-1] != "1" else "2")
        with self.assertRaisesRegex(TrxQuoteError, "checksum"):
            self.issue(receiver_address=bad)

    def test_receiver_must_be_from_protected_configuration(self):
        with self.assertRaisesRegex(TrxQuoteError, "receiver_not_in_protected_registry"):
            self.issue(trusted_receiver_address=valid_tron_address(2))

    def test_secret_must_have_256_bits(self):
        with self.assertRaisesRegex(TrxQuoteError, "protected_signing_secret"):
            self.issue(signing_secret=b"weak")

    def test_invoice_id_must_be_bounded_slug(self):
        for invoice in ("abc", "customer@example.com", "../invoice", "X" * 65, ""):
            with self.subTest(invoice=invoice), self.assertRaisesRegex(TrxQuoteError, "invoice_id_invalid"):
                self.issue(invoice_id=invoice)

    def test_invoice_lifetime_cannot_be_below_one_minute(self):
        with self.assertRaisesRegex(TrxQuoteError, "quote_lifetime_invalid"):
            self.issue(lifetime_seconds=59)

    def test_invoice_lifetime_cannot_exceed_fifteen_minutes(self):
        with self.assertRaisesRegex(TrxQuoteError, "quote_lifetime_invalid"):
            self.issue(lifetime_seconds=901)

    def test_bool_cannot_be_invoice_lifetime(self):
        with self.assertRaisesRegex(TrxQuoteError, "quote_lifetime_invalid"):
            self.issue(lifetime_seconds=True)

    def test_usd_offer_cannot_be_sent_to_tron_without_fx_policy(self):
        usd_offer = replace(self.offer, price=Decimal("12.00"), currency="USD")
        usd_intent = replace(self.intent, price=Decimal("12.00"), currency="USD")
        pending = build_pending_order_record(usd_intent, self.route, usd_offer, now=NOW)
        with self.assertRaisesRegex(TrxQuoteError, "tron_only_quote"):
            self.issue(pending_order=pending, offer=usd_offer)

    def test_stale_customer_intent_rejected(self):
        pending = dict(self.pending, requested_at="2026-11-12T11:59:00Z")
        with self.assertRaisesRegex(TrxQuoteError, "pending_order_contract_invalid"):
            self.issue(pending_order=pending)

    def test_future_customer_intent_rejected(self):
        pending = dict(self.pending, requested_at="2026-11-15T12:02:00Z")
        with self.assertRaisesRegex(TrxQuoteError, "pending_order_contract_invalid"):
            self.issue(pending_order=pending)

    def test_any_canonical_record_mutation_fails(self):
        for changes in ({"state": "paid"}, {"entitlement_granted": True},
                        {"receipt_issued": True}, {"settlement_verified": True},
                        {"delivery_verified": True}, {"payment_required": False},
                        {"financial_signal": True}):
            with self.subTest(changes=changes), self.assertRaisesRegex(
                TrxQuoteError, "pending_order_not_canonical"
            ):
                self.issue(pending_order=dict(self.pending, **changes))

    def test_cannot_add_untrusted_extra_claim_to_record(self):
        with self.assertRaisesRegex(TrxQuoteError, "pending_order_not_canonical"):
            self.issue(pending_order=dict(self.pending, wire_paid=True))

    def test_mismatched_tenant_cannot_reuse_invoice(self):
        with self.assertRaisesRegex(TrxQuoteError, "pending_order_contract_invalid"):
            self.issue(pending_order=dict(self.pending, tenant_id="another"))

    def test_mismatched_offer_cannot_reuse_invoice(self):
        with self.assertRaisesRegex(TrxQuoteError, "pending_order_contract_invalid"):
            self.issue(pending_order=dict(self.pending, offer_id="another"))

    def test_mismatched_price_cannot_reuse_invoice(self):
        with self.assertRaisesRegex(TrxQuoteError, "pending_order_contract_invalid"):
            self.issue(pending_order=dict(self.pending, price="0.000001"))

    def test_wrong_bot_identity_rejected(self):
        with self.assertRaisesRegex(TrxQuoteError, "pending_order_contract_invalid"):
            self.issue(pending_order=dict(self.pending, bot_identity="another.bot.ai"))

    def test_quote_does_not_expose_plain_customer_details(self):
        q = self.issue()
        self.assertNotIn("private-customer", str(q))
        self.assertNotIn("email@", q.signed_token)

    def test_mutated_token_has_invalid_signature(self):
        q = self.issue()
        token = q.signed_token
        mutated = token[:len(token)//2] + ("A" if token[len(token)//2] != "A" else "B") + token[len(token)//2+1:]
        with self.assertRaises(TrxQuoteError):
            self.verify(q, token=mutated)

    def test_unknown_signature_key_denied(self):
        with self.assertRaisesRegex(TrxQuoteError, "signature_invalid"):
            self.verify(self.issue(), signing_secret=b"wrong-key-" + b"z" * 64)

    def test_quote_expires_exactly_at_expiry(self):
        q = self.issue()
        with self.assertRaisesRegex(TrxQuoteError, "quote_expired"):
            self.verify(q, now=NOW + timedelta(minutes=10))

    def test_quote_is_valid_just_before_expiry(self):
        self.verify(self.issue(), now=NOW + timedelta(minutes=9, seconds=59))

    def test_valid_signature_still_cannot_claim_paid(self):
        q = self.issue()
        with self.assertRaisesRegex(TrxQuoteError, "paid_state_prohibited"):
            self.verify(q, token=self.resign(q, state="paid"))

    def test_valid_signature_still_cannot_redirect_receiver(self):
        q = self.issue()
        with self.assertRaisesRegex(TrxQuoteError, "receiver_not_in_protected_registry"):
            self.verify(q, token=self.resign(q, receiver_address=valid_tron_address(2)))

    def test_valid_signature_still_cannot_raise_amount(self):
        q = self.issue()
        with self.assertRaisesRegex(TrxQuoteError, "quote_price_mismatch"):
            self.verify(q, token=self.resign(q, amount_sun=q.amount_sun + 1))

    def test_valid_signature_still_cannot_extend_expiry_beyond_policy(self):
        q = self.issue()
        with self.assertRaisesRegex(TrxQuoteError, "quote_lifetime_invalid"):
            self.verify(q, token=self.resign(q, expires_at="2026-11-15T18:00:00Z"))

    def test_valid_signature_still_cannot_cross_tenant(self):
        q = self.issue()
        with self.assertRaisesRegex(TrxQuoteError, "quote_scope_mismatch"):
            self.verify(q, token=self.resign(q, canonical_host="evil.example"))

    def test_valid_signature_rejects_wrong_network(self):
        q = self.issue()
        with self.assertRaisesRegex(TrxQuoteError, "tron_only_quote"):
            self.verify(q, token=self.resign(q, network="tron-testnet"))

    def test_server_clock_must_be_aware(self):
        with self.assertRaisesRegex(TrxQuoteError, "server_clock"):
            self.issue(now=datetime(2026, 11, 15))

    def test_token_must_not_be_unbounded(self):
        with self.assertRaisesRegex(TrxQuoteError, "token_malformed"):
            self.verify(self.issue(), token="A" * 4097)

    def test_replay_cannot_change_customer_hash(self):
        q = self.issue()
        changed = dict(self.pending, customer_ref_digest=hashlib.sha256(b"other").hexdigest())
        with self.assertRaisesRegex(TrxQuoteError, "quote_scope_mismatch"):
            self.verify(q, pending_order=changed)

    def test_disallowed_financial_offer_cannot_be_quoted(self):
        bad = replace(self.offer, financial_calls_enabled=True)
        with self.assertRaisesRegex(TrxQuoteError, "pending_order_contract_invalid"):
            self.issue(offer=bad)


if __name__ == "__main__":
    unittest.main()
