"""Django integration of the internal no-charge guest email purchase proposal."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib

from django.test import TestCase, override_settings

from core.mojtaba_signal_service_contract import (
    BOT_IDENTITY, SignalOffer, SignalServiceKind, SignalTenantRoute,
)
from .approved_catalog import approved_offer_fingerprint
from .buyer_identity import (
    SignalBuyerIdentityError, canonical_buyer_email,
    buyer_ref_digest, verify_buyer_ref_digest,
)
from .models import PendingSignalOrderRecord, PendingSignalTrxQuote
from .purchase_flow import (
    SignalPurchaseProposalError, start_guest_nonfinancial_signal_purchase,
)
from .test_trx_quotes import RECEIVER

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
BUYER_SECRET = bytes.fromhex("e3" * 32)
EMAIL = "purchaser@real-client.net"


@override_settings(
    MOJTABA_SIGNAL_TRON_QUOTE_ENABLED=True,
    MOJTABA_SIGNAL_CANONICAL_HOST="mojplaywin.com",
    MOJTABA_SIGNAL_TRON_RECEIVER=RECEIVER,
    MOJTABA_SIGNAL_TRON_QUOTE_HMAC_KEY_HEX="d1" * 32,
    MOJTABA_SIGNAL_BUYER_HMAC_KEY_HEX="e3" * 32,
)
class SignalGuestPurchaseFlowTests(TestCase):
    def setUp(self):
        self.route = SignalTenantRoute(
            tenant_id="mojplaywin", canonical_host="mojplaywin.com",
            path_prefix="/signals/", language="en", active=True,
            owner_approved=True, legal_reviewed=True,
        )
        self.offer = SignalOffer(
            offer_id="economic-report", tenant_id="mojplaywin",
            bot_identity=BOT_IDENTITY, language="en",
            service_kind=SignalServiceKind.ECONOMIC_REPORT,
            price=Decimal("8.75"), currency="TRX",
            owner_approved=True, legal_reviewed=True,
            rights_cleared=True, active=True,
        )
        self.allowlist = override_settings(
            MOJTABA_SIGNAL_APPROVED_SERVICE_FINGERPRINTS=[
                approved_offer_fingerprint(self.route, self.offer),
            ],
        )
        self.allowlist.enable()
        self.addCleanup(self.allowlist.disable)

    def start(self, **changes):
        params = dict(
            buyer_email=EMAIL, order_id="order-0001",
            trusted_route=self.route, trusted_offer=self.offer, now=NOW,
        )
        params.update(changes)
        return start_guest_nonfinancial_signal_purchase(**params)

    def test_order_and_quote_created_atomically(self):
        result = self.start()
        self.assertTrue(result.order_created)
        self.assertTrue(result.quote_created)
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 1)
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 1)

    def test_purchase_returns_no_paid_or_entitled_state(self):
        result = self.start()
        self.assertFalse(result.payment_confirmed)
        self.assertFalse(result.delivered)
        self.assertFalse(result.entitlement_granted)
        self.assertFalse(result.email_sent)
        self.assertEqual(result.state, "pending_external_settlement")

    def test_invoice_id_is_stable_under_idempotent_retry(self):
        first = self.start()
        second = self.start()
        self.assertFalse(second.order_created)
        self.assertFalse(second.quote_created)
        self.assertEqual(first.invoice_id, second.invoice_id)
        self.assertEqual(first.signed_quote, second.signed_quote)

    def test_second_valid_order_gets_independent_invoice(self):
        first = self.start()
        second = self.start(order_id="order-0002")
        self.assertNotEqual(first.invoice_id, second.invoice_id)
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 2)
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 2)

    def test_changed_email_cannot_claim_existing_order(self):
        self.start()
        with self.assertRaisesRegex(SignalPurchaseProposalError, "identity_or_offer_changed"):
            self.start(buyer_email="other@real-client.net")
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 1)

    def test_email_domain_case_is_normalized_for_replay(self):
        first = self.start()
        second = self.start(buyer_email="purchaser@REAL-CLIENT.NET")
        self.assertEqual(first.signed_quote, second.signed_quote)

    def test_email_local_case_remains_distinct_identity(self):
        self.start()
        with self.assertRaisesRegex(SignalPurchaseProposalError, "identity_or_offer_changed"):
            self.start(buyer_email="Purchaser@real-client.net")

    def test_changed_price_rejected_on_replay(self):
        self.start()
        with self.assertRaises(Exception):
            self.start(trusted_offer=replace(self.offer, price=Decimal("9.00")))
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 1)

    def test_changed_route_path_rejected_on_replay(self):
        self.start()
        with self.assertRaises(Exception):
            self.start(trusted_route=replace(self.route, path_prefix="/different/"))
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 1)

    def test_invalid_email_fails_before_db_write(self):
        for email in ("", "invalid", "a@b", "a..b@site.com", "a@site..com",
                      "a@guest.mojplaywin.com", "a@example.com",
                      "a@site.invalid", "a@site.local"):
            with self.subTest(email=email), self.assertRaises(SignalBuyerIdentityError):
                self.start(buyer_email=email)
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 0)

    def test_no_raw_email_is_stored_in_database(self):
        self.start()
        serialized = str(PendingSignalOrderRecord.objects.get().payload)
        self.assertNotIn(EMAIL, serialized)
        self.assertNotIn("purchaser", serialized)

    def test_buyer_reference_is_a_tenant_keyed_hmac(self):
        self.start()
        digest = PendingSignalOrderRecord.objects.get().payload["customer_ref_digest"]
        self.assertEqual(len(digest), 64)
        self.assertNotEqual(digest, hashlib.sha256(EMAIL.encode()).hexdigest())
        self.assertTrue(verify_buyer_ref_digest(
            provided_digest=digest, buyer_email=EMAIL,
            tenant_id="mojplaywin", secret=BUYER_SECRET,
        ))

    def test_different_tenant_changes_buyer_hmac(self):
        first = buyer_ref_digest(buyer_email=EMAIL, tenant_id="mojplaywin", secret=BUYER_SECRET)
        second = buyer_ref_digest(buyer_email=EMAIL, tenant_id="other", secret=BUYER_SECRET)
        self.assertNotEqual(first, second)

    def test_changed_email_verification_returns_false(self):
        digest = buyer_ref_digest(buyer_email=EMAIL, tenant_id="mojplaywin", secret=BUYER_SECRET)
        self.assertFalse(verify_buyer_ref_digest(
            provided_digest=digest, buyer_email="other@real-client.net",
            tenant_id="mojplaywin", secret=BUYER_SECRET,
        ))

    def test_quote_gate_disabled_rolls_back_pending_order(self):
        with override_settings(MOJTABA_SIGNAL_TRON_QUOTE_ENABLED=False):
            with self.assertRaises(Exception):
                self.start()
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 0)
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 0)

    def test_unapproved_offer_rolls_back_pending_order(self):
        with override_settings(MOJTABA_SIGNAL_APPROVED_SERVICE_FINGERPRINTS=[]):
            with self.assertRaises(Exception):
                self.start()
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 0)

    def test_missing_receiver_rolls_back_pending_order(self):
        with override_settings(MOJTABA_SIGNAL_TRON_RECEIVER=""):
            with self.assertRaises(Exception):
                self.start()
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 0)

    def test_missing_guest_secret_rolls_back_pending_order(self):
        with override_settings(MOJTABA_SIGNAL_BUYER_HMAC_KEY_HEX=""):
            with self.assertRaisesRegex(SignalPurchaseProposalError, "buyer_hmac_key_required"):
                self.start()
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 0)

    def test_all_zero_guest_secret_rejected(self):
        with override_settings(MOJTABA_SIGNAL_BUYER_HMAC_KEY_HEX="0" * 64):
            with self.assertRaisesRegex(SignalPurchaseProposalError, "buyer_hmac_key_required"):
                self.start()

    def test_invalid_order_identifier_rejected(self):
        with self.assertRaisesRegex(SignalPurchaseProposalError, "trusted_order_id_required"):
            self.start(order_id="../../bad")
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 0)

    def test_unknown_route_rejected_before_db_mutation(self):
        with self.assertRaisesRegex(SignalPurchaseProposalError, "trusted_catalog_required"):
            self.start(trusted_route=None)

    def test_unapproved_financial_signal_offer_cannot_create_invoice(self):
        with self.assertRaises(Exception):
            self.start(trusted_offer=replace(self.offer, financial_calls_enabled=True))
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 0)

    def test_buyer_email_canonicalization_requires_no_space(self):
        self.assertEqual(canonical_buyer_email("ALICE@DOMAIN.COM"), "ALICE@domain.com")
        with self.assertRaises(SignalBuyerIdentityError):
            canonical_buyer_email(" alice@domain.com ")

    def test_guest_key_string_is_never_accepted(self):
        with self.assertRaises(SignalBuyerIdentityError):
            buyer_ref_digest(buyer_email=EMAIL, tenant_id="mojplaywin", secret="notbytes")

    def test_expired_quote_is_not_reissued_without_new_order(self):
        self.start()
        with self.assertRaises(Exception):
            self.start(now=NOW + timedelta(minutes=10))
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 1)
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 1)

    def test_server_clock_must_be_aware(self):
        with self.assertRaises(Exception):
            self.start(now=datetime(2026, 11, 15, 12, 0))
        self.assertEqual(PendingSignalTrxQuote.objects.count(), 0)
