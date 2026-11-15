"""Integration verification of unique non-financial TRON invoice proposals."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib

from django.test import TestCase, override_settings

from core.mojtaba_signal_order_contract import SignalOrderIntent
from core.mojtaba_signal_service_contract import (
    BOT_IDENTITY, SignalOffer, SignalServiceKind, SignalTenantRoute,
)
from .models import PendingSignalOrderRecord, PendingSignalTrxQuote
from .service import persist_pending_order
from .quote_service import (
    DurableSignalQuoteError, issue_pending_trx_quote, read_pending_trx_quote,
)
from .approved_catalog import approved_offer_fingerprint

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
KEY_HEX = "d1" * 32
_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def address(byte):
    payload = b"\x41" + bytes([byte]) * 20
    raw = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    number = int.from_bytes(raw, "big")
    value = ""
    while number:
        number, i = divmod(number, 58)
        value = _BASE58[i] + value
    return value


RECEIVER = address(7)


@override_settings(
    MOJTABA_SIGNAL_TRON_QUOTE_ENABLED=True,
    MOJTABA_SIGNAL_CANONICAL_HOST="mojplaywin.com",
    MOJTABA_SIGNAL_TRON_RECEIVER=RECEIVER,
    MOJTABA_SIGNAL_TRON_QUOTE_HMAC_KEY_HEX=KEY_HEX,
)
class DurableTronQuoteTests(TestCase):
    def setUp(self):
        self.route = SignalTenantRoute(
            tenant_id="mojplaywin", canonical_host="mojplaywin.com",
            path_prefix="/signals/", language="en",
            owner_approved=True, legal_reviewed=True, active=True,
        )
        self.offer = SignalOffer(
            offer_id="economic-report", tenant_id="mojplaywin",
            bot_identity=BOT_IDENTITY, language="en",
            service_kind=SignalServiceKind.ECONOMIC_REPORT,
            price=Decimal("11.500001"), currency="TRX",
            owner_approved=True, legal_reviewed=True, rights_cleared=True,
            active=True,
        )
        self.intent = SignalOrderIntent(
            order_id="order-0001", tenant_id="mojplaywin",
            offer_id="economic-report", bot_identity=BOT_IDENTITY,
            language="en", price=Decimal("11.500001"), currency="TRX",
            customer_ref_digest=hashlib.sha256(b"private-customer-1").hexdigest(),
            requested_at="2026-11-15T11:59:00Z",
        )
        self.persist()
        self.approved_catalog = override_settings(
            MOJTABA_SIGNAL_APPROVED_SERVICE_FINGERPRINTS=[
                approved_offer_fingerprint(self.route, self.offer),
            ],
        )
        self.approved_catalog.enable()
        self.addCleanup(self.approved_catalog.disable)

    def persist(self, intent=None):
        return persist_pending_order(
            intent or self.intent, self.route, self.offer, now=NOW,
        )

    def issue(self, **changes):
        params = dict(
            order_id="order-0001", tenant_id="mojplaywin",
            invoice_id="invoice-0001", trusted_route=self.route,
            trusted_offer=self.offer, now=NOW,
        )
        params.update(changes)
        return issue_pending_trx_quote(**params)

    def read(self, **changes):
        params = dict(
            order_id="order-0001", tenant_id="mojplaywin",
            trusted_route=self.route, trusted_offer=self.offer, now=NOW,
        )
        params.update(changes)
        return read_pending_trx_quote(**params)

    def test_issue_creates_durable_quote_without_payment(self):
        receipt = self.issue()
        self.assertTrue(receipt.created)
        self.assertFalse(receipt.settled)
        self.assertFalse(receipt.delivered)
        self.assertFalse(receipt.entitlement_granted)
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 1)

    def test_proposal_is_exactly_tron_mainnet(self):
        receipt = self.issue()
        self.assertEqual(receipt.state, "pending_external_settlement")
        self.assertTrue(receipt.signed_token)
        self.assertNotIn("private-customer-1", receipt.signed_token)

    def test_replay_same_invoice_returns_exact_token(self):
        first = self.issue()
        replay = self.issue()
        self.assertFalse(replay.created)
        self.assertEqual(replay.signed_token, first.signed_token)
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 1)

    def test_same_order_cannot_be_reinvoiced_with_different_id(self):
        self.issue()
        with self.assertRaisesRegex(DurableSignalQuoteError, "different_quote"):
            self.issue(invoice_id="invoice-9999")
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 1)

    def test_two_orders_cannot_share_invoice_identifier(self):
        self.issue()
        self.persist(replace(
            self.intent, order_id="order-0002",
            customer_ref_digest=hashlib.sha256(b"another").hexdigest(),
        ))
        with self.assertRaisesRegex(DurableSignalQuoteError, "invoice_id_already_used"):
            self.issue(order_id="order-0002")
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 1)

    def test_two_orders_can_have_distinct_quote_ids(self):
        self.issue()
        self.persist(replace(self.intent, order_id="order-0002"))
        other = self.issue(order_id="order-0002", invoice_id="invoice-0002")
        self.assertTrue(other.created)
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 2)

    def test_read_existing_quote_by_exact_tenant(self):
        first = self.issue()
        result = self.read()
        self.assertFalse(result.created)
        self.assertEqual(result.signed_token, first.signed_token)

    def test_cross_tenant_read_is_not_found(self):
        self.issue()
        self.assertIsNone(self.read(tenant_id="another"))

    def test_cross_tenant_issuance_is_denied(self):
        with self.assertRaisesRegex(DurableSignalQuoteError, "not_found"):
            self.issue(tenant_id="another")

    def test_unknown_order_fails_closed(self):
        with self.assertRaisesRegex(DurableSignalQuoteError, "not_found"):
            self.issue(order_id="order-unknown")

    def test_read_of_missing_quote_returns_none(self):
        self.assertIsNone(self.read())

    def test_invalid_order_id_rejected(self):
        with self.assertRaisesRegex(DurableSignalQuoteError, "trusted_quote_identity"):
            self.issue(order_id="../private")

    def test_invalid_tenant_id_rejected(self):
        with self.assertRaisesRegex(DurableSignalQuoteError, "trusted_quote_identity"):
            self.read(tenant_id="UPPER")

    def test_invalid_invoice_id_rejected(self):
        with self.assertRaisesRegex(DurableSignalQuoteError, "trusted_quote_identity"):
            self.issue(invoice_id="a")

    def test_disabled_issuance_gate_is_fail_closed(self):
        with override_settings(MOJTABA_SIGNAL_TRON_QUOTE_ENABLED=False):
            with self.assertRaisesRegex(DurableSignalQuoteError, "issuance_disabled"):
                self.issue()
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 0)

    def test_only_literal_true_enables_quote(self):
        with override_settings(MOJTABA_SIGNAL_TRON_QUOTE_ENABLED=1):
            with self.assertRaisesRegex(DurableSignalQuoteError, "issuance_disabled"):
                self.issue()

    def test_unconfigured_host_rejected(self):
        with override_settings(MOJTABA_SIGNAL_CANONICAL_HOST=""):
            with self.assertRaisesRegex(DurableSignalQuoteError, "merchant_scope"):
                self.issue()

    def test_unapproved_host_rejected(self):
        with override_settings(MOJTABA_SIGNAL_CANONICAL_HOST="other.example"):
            with self.assertRaisesRegex(DurableSignalQuoteError, "merchant_scope"):
                self.issue()

    def test_missing_receiver_rejected(self):
        with override_settings(MOJTABA_SIGNAL_TRON_RECEIVER=""):
            with self.assertRaisesRegex(DurableSignalQuoteError, "protected_receiver"):
                self.issue()

    def test_invalid_receiver_checksum_rejected(self):
        with override_settings(MOJTABA_SIGNAL_TRON_RECEIVER=RECEIVER[:-1] + ("1" if RECEIVER[-1] != "1" else "2")):
            from core.mojtaba_signal_tron_invoice_contract import TrxQuoteError
            with self.assertRaises(TrxQuoteError):
                self.issue()

    def test_invalid_key_length_rejected(self):
        with override_settings(MOJTABA_SIGNAL_TRON_QUOTE_HMAC_KEY_HEX="abc"):
            with self.assertRaisesRegex(DurableSignalQuoteError, "hmac_key"):
                self.issue()

    def test_all_zero_key_rejected(self):
        with override_settings(MOJTABA_SIGNAL_TRON_QUOTE_HMAC_KEY_HEX="0" * 64):
            with self.assertRaisesRegex(DurableSignalQuoteError, "hmac_key"):
                self.issue()

    def test_expired_quote_cannot_be_replayed(self):
        self.issue()
        with self.assertRaisesRegex(DurableSignalQuoteError, "verification_failed"):
            self.issue(now=NOW + timedelta(minutes=10))

    def test_expired_quote_cannot_be_read_as_active(self):
        self.issue()
        with self.assertRaisesRegex(DurableSignalQuoteError, "verification_failed"):
            self.read(now=NOW + timedelta(minutes=10))

    def test_forged_token_is_rejected(self):
        self.issue()
        row = PendingSignalTrxQuote.objects.get()
        row.signed_token = "forged"
        row.save(update_fields=["signed_token"])
        with self.assertRaisesRegex(DurableSignalQuoteError, "integrity_invalid"):
            self.read()

    def test_forged_token_with_fake_digest_still_fails_hmac(self):
        self.issue()
        row = PendingSignalTrxQuote.objects.get()
        row.signed_token = "AA.AA"
        row.token_digest = hashlib.sha256(row.signed_token.encode()).hexdigest()
        row.save(update_fields=["signed_token", "token_digest"])
        with self.assertRaisesRegex(DurableSignalQuoteError, "verification_failed"):
            self.read()

    def test_modified_invoice_id_does_not_escape_integrity(self):
        self.issue()
        row = PendingSignalTrxQuote.objects.get()
        row.invoice_id = "invoice-altered"
        row.save(update_fields=["invoice_id"])
        with self.assertRaisesRegex(DurableSignalQuoteError, "invoice_mismatch"):
            self.read()

    def test_changed_signing_key_revokes_existing_token(self):
        self.issue()
        with override_settings(MOJTABA_SIGNAL_TRON_QUOTE_HMAC_KEY_HEX="a2" * 32):
            with self.assertRaisesRegex(DurableSignalQuoteError, "verification_failed"):
                self.read()

    def test_changed_receiver_revokes_existing_token(self):
        self.issue()
        with override_settings(MOJTABA_SIGNAL_TRON_RECEIVER=address(9)):
            with self.assertRaisesRegex(DurableSignalQuoteError, "verification_failed"):
                self.read()

    def test_changed_offer_price_does_not_validate_existing_invoice(self):
        self.issue()
        altered = replace(self.offer, price=Decimal("99.99"))
        with self.assertRaisesRegex(DurableSignalQuoteError, "protected_approved_catalog"):
            self.read(trusted_offer=altered)

    def test_paid_flag_added_to_pending_order_detected(self):
        self.issue()
        row = PendingSignalOrderRecord.objects.get()
        row.payload["settlement_verified"] = True
        row.save(update_fields=["payload"])
        from .service import DurableSignalOrderError
        with self.assertRaises(DurableSignalOrderError):
            self.read()

    def test_quoted_payment_does_not_set_order_paid(self):
        self.issue()
        row = PendingSignalOrderRecord.objects.get()
        self.assertFalse(row.payload["settlement_verified"])
        self.assertFalse(row.payload["entitlement_granted"])
        self.assertFalse(row.payload["receipt_issued"])

    def test_trx_only_no_implicit_usd_fx(self):
        self.assertEqual(self.offer.currency, "TRX")
        self.assertEqual(self.issue().state, "pending_external_settlement")
    def test_missing_approved_service_catalog_denies_quote(self):
        with override_settings(MOJTABA_SIGNAL_APPROVED_SERVICE_FINGERPRINTS=[]):
            with self.assertRaisesRegex(DurableSignalQuoteError, "protected_approved_catalog"):
                self.issue()
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 0)

    def test_wrong_approved_service_fingerprint_denies_quote(self):
        with override_settings(MOJTABA_SIGNAL_APPROVED_SERVICE_FINGERPRINTS=["a" * 64]):
            with self.assertRaisesRegex(DurableSignalQuoteError, "protected_approved_catalog"):
                self.issue()

    def test_invalid_allowlist_type_denies_quote(self):
        for invalid in (None, "", "a" * 64, [1], ["x"], ["A" * 64]):
            with self.subTest(invalid=repr(invalid)[:20]):
                with override_settings(MOJTABA_SIGNAL_APPROVED_SERVICE_FINGERPRINTS=invalid):
                    with self.assertRaisesRegex(DurableSignalQuoteError, "protected_approved_catalog"):
                        self.issue()

    def test_unapproved_offer_language_denies_quote(self):
        altered = replace(self.offer, language="fa")
        with self.assertRaises(DurableSignalQuoteError):
            self.issue(trusted_offer=altered)

    def test_unapproved_offer_price_change_denies_quote(self):
        altered = replace(self.offer, price=Decimal("12.0"))
        with self.assertRaisesRegex(DurableSignalQuoteError, "protected_approved_catalog"):
            self.issue(trusted_offer=altered)

    def test_unapproved_route_path_change_denies_quote(self):
        altered = replace(self.route, path_prefix="/different/")
        with self.assertRaisesRegex(DurableSignalQuoteError, "protected_approved_catalog"):
            self.issue(trusted_route=altered)

    def test_unapproved_route_host_change_denies_quote(self):
        altered = replace(self.route, canonical_host="different.example")
        with self.assertRaisesRegex(DurableSignalQuoteError, "protected_approved_catalog"):
            self.issue(trusted_route=altered)

    def test_missing_route_object_is_domain_error(self):
        with self.assertRaisesRegex(DurableSignalQuoteError, "protected_service_contract"):
            self.issue(trusted_route=None)

    def test_missing_offer_object_is_domain_error(self):
        with self.assertRaisesRegex(DurableSignalQuoteError, "protected_service_contract"):
            self.issue(trusted_offer=None)

    def test_reusing_buyer_identity_key_for_quote_signing_denied(self):
        with override_settings(MOJTABA_SIGNAL_BUYER_HMAC_KEY_HEX=KEY_HEX):
            with self.assertRaisesRegex(DurableSignalQuoteError, "signing_keys_must_differ"):
                self.issue()
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 0)

    def test_hex_case_change_cannot_bypass_key_separation(self):
        with override_settings(MOJTABA_SIGNAL_BUYER_HMAC_KEY_HEX=KEY_HEX.upper()):
            with self.assertRaisesRegex(DurableSignalQuoteError, "signing_keys_must_differ"):
                self.issue()
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 0)
