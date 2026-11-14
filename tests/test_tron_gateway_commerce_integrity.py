"""Real Django database integrity tests; never sends funds, email or RPC calls."""
import hashlib
import tempfile
import time
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, RequestFactory, override_settings
from django.http import Http404
from django.db import transaction, IntegrityError

from core.models import LedgerEntry, Order, PaymentIntent, PaymentWebhookEvent, Product, TronMainnetSettlementClaim
from core.tron_gateway_invoice import TronGatewayInvoice
from core.tron_gateway_verify import MAINNET_RECEIVER
from core.tron_gateway_web import (
    PROVIDER, _email_key, _host, _new_invoice, _owner,
    _read_product, _record_paid,
)

PROOF = {
    "txid": "a" * 64,
    "sender_hex": "41" + "c" * 40,
    "block_height": 9999999,
    "block_time_ms": 1800000000000,
    "proof_digest": "b" * 64,
    "finality": "solidified",
}


@override_settings(TRON_UNIFIED_SETTLEMENT_EXCLUSIVE_CONFIRMED=True)
class CommerceGatewayIntegrityTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title="Approved service plan",
            product_type="service",
            active=True,
            price=Decimal("12.00"),
            currency="USD",
            metadata={
                "rights_cleared": True, "publication_approved": True,
                "sales_enabled": True, "in_stock": True,
                "fulfillment_ready": True, "fulfillment_type": "service",
                "tron_price_sun": 999999,
                "tron_price_currency": "USD",
                "tron_price_reference_amount": "12.00",
                "tron_quote_valid_until_ms": int(time.time() * 1000) + 3_600_000,
            },
        )

    def _issue(self, email="paying@example.com", host="mojplaywin.com"):
        inv, token = _new_invoice(email, host, "en", self.product.pk)
        self.assertTrue(token)
        return inv

    def _payable(self, email="paying@example.com"):
        invoice = self._issue(email)
        TronGatewayInvoice.objects.filter(pk=invoice.pk).update(status="awaiting_payment")
        return TronGatewayInvoice.objects.get(pk=invoice.pk)

    def test_guest_invoice_is_persisted_and_ledger_is_unpaid(self):
        invoice = self._issue()
        self.assertEqual(invoice.order.status, "pending")
        self.assertEqual(invoice.payment_intent.status, "awaiting_payment")
        self.assertEqual(invoice.status, "email_pending")
        self.assertFalse(invoice.order.customer.has_usable_password())
        self.assertEqual(invoice.order.items.count(), 1)
        self.assertEqual(LedgerEntry.objects.count(), 0)

    def test_registered_intent_and_invoice_never_share_a_quote_amount(self):
        a = self._issue()
        b = self._issue("another@example.com")
        self.assertNotEqual(a.amount_sun, b.amount_sun)
        self.assertEqual(TronGatewayInvoice.objects.count(), 2)

    def test_unverified_email_must_not_be_credited(self):
        invoice = self._issue()
        self.assertFalse(_record_paid(invoice.pk, PROOF))
        self.assertFalse(LedgerEntry.objects.exists())

    def test_immutable_paid_credit_recorded_exactly_once(self):
        invoice = self._payable()
        self.assertTrue(_record_paid(invoice.pk, PROOF))
        self.assertTrue(_record_paid(invoice.pk, PROOF))
        invoice.refresh_from_db()
        invoice.order.refresh_from_db()
        invoice.payment_intent.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(invoice.order.status, "paid")
        self.assertEqual(invoice.payment_intent.status, "paid")
        self.assertEqual(PaymentWebhookEvent.objects.filter(event_id=PROOF["txid"]).count(), 1)
        self.assertEqual(LedgerEntry.objects.count(), 1)
        self.assertEqual(TronMainnetSettlementClaim.objects.count(), 1)
        self.assertEqual(
            LedgerEntry.objects.get().metadata["source_host"], "mojplaywin.com")

    def test_old_provider_transaction_cannot_be_double_credited(self):
        invoice = self._payable()
        PaymentWebhookEvent.objects.create(
            provider="mpw_walletless_trx_v1", event_id=PROOF["txid"],
            event_type="tron_finalized", payload_hash="a"*64, status="processed")
        self.assertFalse(_record_paid(invoice.pk, PROOF))
        self.assertFalse(LedgerEntry.objects.exists())


    def test_legacy_uppercase_event_txid_cannot_be_double_credited(self):
        invoice = self._payable()
        PaymentWebhookEvent.objects.create(
            provider="mpw_walletless_trx_v1", event_id=PROOF["txid"].upper(),
            event_type="tron_finalized", payload_hash="f"*64, status="processed")
        self.assertFalse(_record_paid(invoice.pk, PROOF))
        self.assertFalse(LedgerEntry.objects.exists())

    def test_legacy_uppercase_ledger_reference_cannot_be_double_credited(self):
        invoice = self._payable()
        LedgerEntry.objects.create(
            order=invoice.order, payment_intent=invoice.payment_intent,
            entry_type="credit", amount=invoice.order.total,
            currency=invoice.order.currency,
            reference="walletless:tron-mainnet:" + PROOF["txid"].upper())
        self.assertFalse(_record_paid(invoice.pk, PROOF))
        self.assertEqual(LedgerEntry.objects.count(), 1)
        self.assertFalse(PaymentWebhookEvent.objects.exists())

    def test_unrelated_legacy_event_does_not_block_a_valid_invoice(self):
        invoice = self._payable()
        PaymentWebhookEvent.objects.create(
            provider="mpw_walletless_trx_v1", event_id="c"*64,
            event_type="tron_finalized", payload_hash="f"*64, status="processed")
        self.assertTrue(_record_paid(invoice.pk, PROOF))
        self.assertEqual(LedgerEntry.objects.count(), 1)

    def test_paid_order_with_changed_status_not_overwritten(self):
        invoice = self._payable()
        Order.objects.filter(pk=invoice.order_id).update(status="cancelled")
        self.assertFalse(_record_paid(invoice.pk, PROOF))
        self.assertEqual(Order.objects.get(pk=invoice.order_id).status, "cancelled")
        self.assertEqual(LedgerEntry.objects.count(), 0)

    def test_replay_same_txid_into_second_invoice_is_rejected(self):
        one = self._payable()
        two = self._payable("another@example.com")
        self.assertTrue(_record_paid(one.pk, PROOF))
        self.assertFalse(_record_paid(two.pk, PROOF))
        self.assertEqual(LedgerEntry.objects.count(), 1)


    @override_settings(TRON_UNIFIED_SETTLEMENT_EXCLUSIVE_CONFIRMED=False)
    def test_missing_exclusive_legacy_writer_proof_prevents_all_new_credits(self):
        invoice = self._payable()
        self.assertFalse(_record_paid(invoice.pk, PROOF))
        self.assertFalse(TronMainnetSettlementClaim.objects.exists())
        self.assertFalse(PaymentWebhookEvent.objects.exists())
        self.assertFalse(LedgerEntry.objects.exists())

    def test_single_canonical_claim_and_idempotent_paid_retry(self):
        invoice = self._payable()
        self.assertTrue(_record_paid(invoice.pk, PROOF))
        self.assertTrue(_record_paid(invoice.pk, PROOF))
        claim = TronMainnetSettlementClaim.objects.get(txid=PROOF["txid"])
        self.assertEqual(claim.payment_intent_id, invoice.payment_intent_id)
        self.assertEqual(claim.invoice_id, invoice.pk)
        self.assertEqual(TronMainnetSettlementClaim.objects.count(), 1)

    def test_nonfinalized_fabricated_proof_denied(self):
        invoice = self._payable()
        self.assertFalse(_record_paid(invoice.pk, dict(PROOF, finality="confirmed")))
        self.assertFalse(TronMainnetSettlementClaim.objects.exists())

    def test_missing_proof_digest_denied(self):
        invoice = self._payable()
        invalid = dict(PROOF)
        invalid.pop("proof_digest")
        self.assertFalse(_record_paid(invoice.pk, invalid))
        self.assertFalse(LedgerEntry.objects.exists())

    def test_invalid_sender_denied_before_db_claim(self):
        invoice = self._payable()
        self.assertFalse(_record_paid(invoice.pk, dict(PROOF, sender_hex="bad")))
        self.assertFalse(TronMainnetSettlementClaim.objects.exists())

    def test_unrelated_preexisting_claim_cannot_block_new_tx(self):
        first = self._payable()
        second = self._payable("other@example.com")
        self.assertTrue(_record_paid(first.pk, dict(PROOF, txid="d"*64)))
        self.assertTrue(_record_paid(second.pk, PROOF))
        self.assertEqual(TronMainnetSettlementClaim.objects.count(), 2)

    def test_claim_primary_key_prevents_unrelated_provider_reuse(self):
        invoice = self._payable()
        TronMainnetSettlementClaim.objects.create(
            txid=PROOF["txid"], provider="mpw_walletless_trx_v1",
            invoice=invoice, payment_intent=invoice.payment_intent,
            proof_digest="c"*64,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                _record_paid(invoice.pk, PROOF)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "awaiting_payment")
        self.assertEqual(TronMainnetSettlementClaim.objects.count(), 1)
        self.assertFalse(LedgerEntry.objects.exists())

    def test_claim_rolls_back_when_financial_event_fails(self):
        invoice = self._payable()
        with patch("core.tron_gateway_web.PaymentWebhookEvent.objects.create",
                   side_effect=IntegrityError("simulated failed event write")):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    _record_paid(invoice.pk, PROOF)
        self.assertFalse(TronMainnetSettlementClaim.objects.exists())
        self.assertFalse(LedgerEntry.objects.exists())
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "awaiting_payment")

    def test_expired_price_quote_cannot_start_sale(self):
        self.product.metadata["tron_quote_valid_until_ms"] = int(time.time() * 1000) - 1
        self.product.save(update_fields=["metadata"])
        with self.assertRaises(Http404):
            _read_product(self.product.pk, "en")

    def test_quote_change_without_approval_invalidates_sale(self):
        self.product.price = Decimal("13.00")
        self.product.save(update_fields=["price"])
        with self.assertRaises(Http404):
            _read_product(self.product.pk, "en")

    def test_unverified_rights_cannot_start_sale(self):
        self.product.metadata["rights_cleared"] = False
        self.product.save(update_fields=["metadata"])
        with self.assertRaises(Http404):
            _read_product(self.product.pk, "en")

    def test_currency_mismatch_denies_cross_brand_quote(self):
        with self.assertRaises(Http404):
            _read_product(self.product.pk, "fa")

    def test_payment_session_must_be_bound_to_exact_host(self):
        invoice = self._issue()
        req = RequestFactory().get("/", secure=True)
        req.session = {
            "tron_verified_email": _email_key(invoice.buyer_email),
            "tron_verified_host": "zomorodmelal.ir",
            "tron_verified_at": int(time.time())}
        with self.assertRaises(Http404):
            _owner(req, invoice.pk, "mojplaywin.com")

    def test_old_payment_session_is_denied(self):
        invoice = self._issue()
        req = RequestFactory().get("/", secure=True)
        req.session = {
            "tron_verified_email": _email_key(invoice.buyer_email),
            "tron_verified_host": "mojplaywin.com",
            "tron_verified_at": int(time.time()) - 1000}
        with self.assertRaises(Http404):
            _owner(req, invoice.pk, "mojplaywin.com")

    def test_private_asset_is_pinned_at_sale_instead_of_catalogue(self):
        from django.test.utils import override_settings
        from core.tron_gateway_delivery import _file_from_private_root
        with tempfile.TemporaryDirectory() as tmpdir:
            data = b"Invoice-specific rights-protected digital material\n"
            Path(tmpdir, "lesson.bin").write_bytes(data)
            md = dict(self.product.metadata)
            md.update({
                "fulfillment_type": "digital",
                "asset_relpath": "lesson.bin",
                "sha256": hashlib.sha256(data).hexdigest(),
                "rights_asset_sha256": hashlib.sha256(data).hexdigest(),
                "rights_document_sha256": "d"*64,
            })
            self.product.metadata = md
            self.product.save(update_fields=["metadata"])
            with override_settings(TRON_UNIFIED_PRIVATE_DIGITAL_ROOT=tmpdir):
                invoice = self._issue()
                self.assertEqual(invoice.asset_relpath_snapshot, "lesson.bin")
                self.assertEqual(invoice.asset_sha256_snapshot, hashlib.sha256(data).hexdigest())
                self.assertEqual(invoice.fulfillment_kind, "digital")
                with _file_from_private_root(invoice.asset_relpath_snapshot,
                                            invoice.asset_sha256_snapshot) as stream:
                    self.assertEqual(stream.read(), data)
            self.product.price = Decimal("14.00")
            self.product.save(update_fields=["price"])
            invoice.refresh_from_db()
            self.assertEqual(invoice.asset_sha256_snapshot, hashlib.sha256(data).hexdigest())

    @override_settings(
        ALLOWED_HOSTS=["mojplaywin.com", "zomorodmelal.ir"],
        TRON_UNIFIED_PUBLIC_ENABLED=True,
        TRON_UNIFIED_SHARED_RATE_LIMIT_READY=True,
        TRON_UNIFIED_RECEIVER=MAINNET_RECEIVER,
        TRON_UNIFIED_ALLOWED_HOSTS=("mojplaywin.com",),
    )
    def test_unlisted_host_cannot_issue_invoice(self):
        request = RequestFactory().get("/", secure=True, HTTP_HOST="zomorodmelal.ir")
        with patch("core.tron_gateway_web._shared_rate_limit_ready", return_value=True):
            with self.assertRaises(Http404):
                _host(request)

    @override_settings(
        ALLOWED_HOSTS=["mojplaywin.com"],
        TRON_UNIFIED_PUBLIC_ENABLED=False,
        TRON_UNIFIED_SHARED_RATE_LIMIT_READY=True,
        TRON_UNIFIED_RECEIVER=MAINNET_RECEIVER,
        TRON_UNIFIED_ALLOWED_HOSTS=("mojplaywin.com",),
    )
    def test_disabled_public_sale_cannot_be_bypassed(self):
        request = RequestFactory().get("/", secure=True, HTTP_HOST="mojplaywin.com")
        with patch("core.tron_gateway_web._shared_rate_limit_ready", return_value=True):
            with self.assertRaises(Http404):
                _host(request)
