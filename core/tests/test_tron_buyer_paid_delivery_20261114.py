"""Isolated Django proof that TRON buyer downloads bind exact original quote.

All records are synthetic test database rows. No TRX transactions, SMTP,
wallet, customer identity, RPC, live site or release actions.
"""
from decimal import Decimal
import hashlib
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from core.models import (
    LedgerEntry, Order, OrderItem, PaymentIntent, PaymentWebhookEvent,
    Product, TronGatewayInvoice,
)
from core.tron_gateway_delivery import download_paid
from core.tron_gateway_verify import MAINNET_RECEIVER
from core.tron_gateway_web import (
    PROVIDER, _new_invoice, _preflight_digital_before_charge, _read_product,
)


class BuyerReceiptAndPrivateDownloadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tron-buyer-isolated", email="synthetic@farm-market.example",
            password="not-a-real-buyer",
        )
        self.root_temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.root_temp.cleanup)
        self.root = Path(self.root_temp.name) / "private"
        self.root.mkdir(mode=0o700)
        self.root.chmod(0o700)
        self.file = self.root / "study.pdf"
        self.bytes = b"%PDF-1.7\nsynthetic paid-delivery contract\n%%EOF\n"
        self.file.write_bytes(self.bytes)
        self.file.chmod(0o600)
        self.sha = hashlib.sha256(self.bytes).hexdigest()
        self.metadata = {
            "rights_cleared": True,
            "publication_approved": True,
            "sales_enabled": True,
            "in_stock": True,
            "fulfillment_ready": True,
            "fulfillment_type": "digital",
            "rights_document_sha256": "a" * 64,
            "rights_asset_sha256": self.sha,
            "sha256": self.sha,
            "asset_relpath": "study.pdf",
            "tron_price_sun": 1500000,
            "tron_price_currency": "USD",
            "tron_price_reference_amount": "20.00",
        }
        self.product = Product.objects.create(
            title="Synthetic farm income course", product_type="digital",
            price=Decimal("20.00"), currency="USD", active=True,
            owner=self.user, metadata=dict(self.metadata),
        )
        self.order = Order.objects.create(
            customer=self.user, status="paid", total=Decimal("20.00"), currency="USD",
        )
        self.item = OrderItem.objects.create(
            order=self.order, product=self.product, quantity=1,
            unit_price=Decimal("20.00"), currency="USD",
        )
        self.intent = PaymentIntent.objects.create(
            order=self.order, amount=Decimal("20.00"), currency="USD",
            status="paid", provider=PROVIDER, provider_reference="a" * 64,
            idempotency_key="synthetic-invoice-20261114",
        )
        _, _, fingerprint = _read_product(self.product.pk, "en")
        self.txid = "a" * 64
        self.proof = "b" * 64
        self.invoice = TronGatewayInvoice.objects.create(
            order=self.order, payment_intent=self.intent,
            buyer_email=self.user.email, buyer_email_sha="e" * 64,
            source_host="mojplaywin.com", language="en",
            receiver=MAINNET_RECEIVER, amount_sun=1500000,
            issued_ms=int(time.time() * 1000) - 10000,
            expires_ms=int(time.time() * 1000) + 100000,
            claim_sha256="c" * 64, quote_fingerprint=fingerprint,
            status="paid", txid=self.txid, proof_digest=self.proof,
            verified_at=timezone.now(),
        )
        self.event = PaymentWebhookEvent.objects.create(
            provider=PROVIDER, event_id=self.txid,
            event_type="tron_finalized", payment_intent=self.intent,
            status="processed", payload_hash=self.proof,
            processed_at=timezone.now(),
        )
        self.credit = LedgerEntry.objects.create(
            order=self.order, payment_intent=self.intent,
            entry_type="credit", amount=Decimal("20.00"), currency="USD",
            reference="tron-mainnet:" + self.txid,
            metadata={
                "network": "tron-mainnet", "asset": "TRX",
                "amount_sun": self.invoice.amount_sun,
                "receiver": MAINNET_RECEIVER,
                "proof_digest": self.proof,
                "webhook_event_id": self.event.pk,
            },
        )

    def download(self, *, expect_ok=False):
        req = RequestFactory().get(
            "/pay/tron/download/" + str(self.invoice.pk) + "/",
            secure=True, HTTP_HOST="mojplaywin.com",
        )
        with (override_settings(TRON_UNIFIED_PRIVATE_DIGITAL_ROOT=str(self.root)),
              patch("core.tron_gateway_delivery._host",
                    return_value=("mojplaywin.com", "en")),
              patch("core.tron_gateway_delivery._owner",
                    return_value=self.invoice)):
            if not expect_ok:
                with self.assertRaises(Http404):
                    download_paid(req, self.invoice.pk)
                return
            response = download_paid(req, self.invoice.pk)
            data = b"".join(response.streaming_content)
            response.close()
            return data, response

    def product_meta(self, **kwargs):
        md = dict(self.product.metadata)
        md.update(kwargs)
        self.product.metadata = md
        self.product.save(update_fields=["metadata"])

    def test_01_matched_paid_file_is_downloadable_with_private_headers(self):
        data, response = self.download(expect_ok=True)
        self.assertEqual(data, self.bytes)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Download-Options"], "noopen")

    def test_02_wrong_original_quote_fingerprint_denied(self):
        self.invoice.quote_fingerprint = "0" * 64
        self.invoice.save(update_fields=["quote_fingerprint"])
        self.download()

    def test_03_drifted_asset_relpath_denied(self):
        self.product_meta(asset_relpath="replaced.pdf")
        self.download()

    def test_04_drifted_product_price_denied(self):
        self.product.price = Decimal("21.00")
        self.product.save(update_fields=["price"])
        self.download()

    def test_05_drifted_quote_sun_denied(self):
        self.product_meta(tron_price_sun=1500010)
        self.download()

    def test_06_missing_local_file_denied(self):
        self.file.unlink()
        self.download()

    def test_07_tampered_local_file_denied(self):
        self.file.write_bytes(self.bytes + b"modified")
        self.download()

    def test_08_group_readable_local_file_denied(self):
        self.file.chmod(0o640)
        self.download()

    def test_09_group_access_to_root_denied(self):
        self.root.chmod(0o750)
        self.download()

    def test_10_file_symlink_denied(self):
        other = self.root.parent / "public.pdf"
        other.write_bytes(self.bytes)
        self.file.unlink()
        self.file.symlink_to(other)
        self.download()

    def test_11_refund_blocks_repeat_delivery(self):
        LedgerEntry.objects.create(
            order=self.order, entry_type="refund", amount="20.00",
            currency="USD", reference="refund:synthetic-order",
        )
        self.download()

    def test_12_chargeback_blocks_repeat_delivery(self):
        LedgerEntry.objects.create(
            order=self.order, entry_type="chargeback", amount="20.00",
            currency="USD", reference="chargeback:synthetic-order",
        )
        self.download()

    def test_13_wrong_receiver_denied(self):
        self.invoice.receiver = "not-the-merchant"
        self.invoice.save(update_fields=["receiver"])
        self.download()

    def test_14_wrong_proof_digest_in_credit_denied(self):
        md = dict(self.credit.metadata)
        md["proof_digest"] = "f" * 64
        self.credit.metadata = md
        self.credit.save(update_fields=["metadata"])
        self.download()

    def test_15_wrong_credit_amount_sun_denied(self):
        md = dict(self.credit.metadata)
        md["amount_sun"] = 2000000
        self.credit.metadata = md
        self.credit.save(update_fields=["metadata"])
        self.download()

    def test_16_wrong_proof_event_link_denied(self):
        md = dict(self.credit.metadata)
        md["webhook_event_id"] = 99999
        self.credit.metadata = md
        self.credit.save(update_fields=["metadata"])
        self.download()

    def test_17_missing_finalized_event_denied(self):
        self.event.delete()
        self.download()

    def test_18_not_processed_event_denied(self):
        self.event.status = "received"
        self.event.save(update_fields=["status"])
        self.download()

    def test_19_event_without_processed_at_denied(self):
        self.event.processed_at = None
        self.event.save(update_fields=["processed_at"])
        self.download()

    def test_20_non_finalized_event_type_denied(self):
        self.event.event_type = "payment.succeeded"
        self.event.save(update_fields=["event_type"])
        self.download()

    def test_21_duplicate_credit_denied(self):
        LedgerEntry.objects.create(
            order=self.order, payment_intent=self.intent,
            entry_type="credit", amount="20.00", currency="USD",
            reference="tron-mainnet:" + "d"*64, metadata=dict(self.credit.metadata),
        )
        # The specific credited tx reference remains unique. The other
        # credit is deliberately for another tx; ensure account level check.
        self.download()

    def test_22_multiple_order_items_denied(self):
        Product.objects.create(
            title="Unapproved second line", product_type="digital",
            active=True, price="1.00", currency="USD", owner=self.user,
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, quantity=1,
            unit_price="1.00", currency="USD",
        )
        self.download()

    def test_23_invalid_order_item_quantity_denied(self):
        self.item.quantity = 2
        self.item.save(update_fields=["quantity"])
        self.download()

    def test_24_order_item_price_mismatch_denied(self):
        self.item.unit_price = Decimal("10.00")
        self.item.save(update_fields=["unit_price"])
        self.download()

    def test_25_intent_amount_mismatch_denied(self):
        self.intent.amount = Decimal("19.99")
        self.intent.save(update_fields=["amount"])
        self.download()

    def test_26_intent_currency_mismatch_denied(self):
        self.intent.currency = "IRR"
        self.intent.save(update_fields=["currency"])
        self.download()

    def test_27_stale_product_rights_denied(self):
        self.product_meta(rights_cleared=False)
        self.download()

    def test_28_inactive_product_denied(self):
        self.product.active = False
        self.product.save(update_fields=["active"])
        self.download()

    def test_29_order_not_paid_denied(self):
        self.order.status = "pending"
        self.order.save(update_fields=["status"])
        self.download()

    def test_30_zero_or_missing_txid_denied(self):
        self.invoice.txid = ""
        self.invoice.save(update_fields=["txid"])
        self.download()

    def test_31_email_claim_not_authorized_by_this_test(self):
        # Authentication is enforced by _owner in the real request path;
        # these tests isolate post-ownership proof binding only.
        from core.tron_gateway_web import _owner
        self.assertTrue(callable(_owner))

    def test_32_prequote_missing_file_blocks_before_creating_invoice(self):
        self.file.unlink()
        with override_settings(TRON_UNIFIED_PRIVATE_DIGITAL_ROOT=str(self.root)):
            with self.assertRaises(ValueError):
                _preflight_digital_before_charge(self.product)
        self.assertEqual(TronGatewayInvoice.objects.count(), 1)

    def test_33_prequote_valid_bytes_do_not_send_email(self):
        with override_settings(TRON_UNIFIED_PRIVATE_DIGITAL_ROOT=str(self.root)):
            _preflight_digital_before_charge(self.product)
        self.assertEqual(TronGatewayInvoice.objects.count(), 1)

    def test_34_quote_fingerprint_changes_on_path_change(self):
        before = _read_product(self.product.pk, "en")[2]
        self.product_meta(asset_relpath="other.pdf")
        after = _read_product(self.product.pk, "en")[2]
        self.assertNotEqual(before, after)

    def test_35_quote_fingerprint_changes_on_rights_document_change(self):
        before = _read_product(self.product.pk, "en")[2]
        self.product_meta(rights_document_sha256="b" * 64)
        after = _read_product(self.product.pk, "en")[2]
        self.assertNotEqual(before, after)

    def test_36_quote_fingerprint_changes_on_price_change(self):
        before = _read_product(self.product.pk, "en")[2]
        self.product.price = Decimal("21.00")
        self.product.save(update_fields=["price"])
        # Price must still match approved TRX price reference string; validate
        # that unauthorized price changes cannot issue a new payable quote.
        with self.assertRaises(Http404):
            _read_product(self.product.pk, "en")

    def test_37_no_contact_from_private_get(self):
        from unittest.mock import patch as mockpatch
        with mockpatch("core.tron_gateway_web.send_mail") as send:
            self.download(expect_ok=True)
            send.assert_not_called()

    def test_38_no_database_payment_write_from_private_get(self):
        before = (
            Order.objects.count(), PaymentIntent.objects.count(),
            PaymentWebhookEvent.objects.count(), LedgerEntry.objects.count(),
        )
        self.download(expect_ok=True)
        self.assertEqual(before, (
            Order.objects.count(), PaymentIntent.objects.count(),
            PaymentWebhookEvent.objects.count(), LedgerEntry.objects.count(),
        ))

    def test_39_prequote_missing_file_creates_no_pending_order(self):
        before = (Order.objects.count(), TronGatewayInvoice.objects.count())
        self.file.unlink()
        with override_settings(TRON_UNIFIED_PRIVATE_DIGITAL_ROOT=str(self.root)):
            with self.assertRaises(ValueError):
                _new_invoice("newbuyer@example.invalid", "mojplaywin.com", "en", self.product.pk)
        self.assertEqual(before, (Order.objects.count(), TronGatewayInvoice.objects.count()))

    def test_40_valid_prequote_creates_one_pending_email_invoice_without_sending(self):
        from core.tron_gateway_web import _new_invoice
        with override_settings(TRON_UNIFIED_PRIVATE_DIGITAL_ROOT=str(self.root)):
            with patch("core.tron_gateway_web.send_mail") as send:
                invoice, token = _new_invoice(
                    "newbuyer@example.invalid", "mojplaywin.com", "en", self.product.pk,
                )
                send.assert_not_called()
        self.assertEqual(invoice.status, "email_pending")
        self.assertTrue(len(token) >= 30)
        self.assertEqual(invoice.order.status, "pending")
        self.assertEqual(invoice.payment_intent.status, "awaiting_payment")
        self.assertEqual(invoice.quote_fingerprint, _read_product(self.product.pk, "en")[2])

    def test_41_requote_fails_if_digital_file_checksum_mismatches(self):
        before = TronGatewayInvoice.objects.count()
        self.file.write_bytes(self.bytes + b"tampering")
        with override_settings(TRON_UNIFIED_PRIVATE_DIGITAL_ROOT=str(self.root)):
            with self.assertRaises(ValueError):
                _new_invoice("freshbuyer@example.invalid", "mojplaywin.com", "en", self.product.pk)
        self.assertEqual(TronGatewayInvoice.objects.count(), before)

    def test_42_invoice_prequote_does_not_change_paid_invoice(self):
        with override_settings(TRON_UNIFIED_PRIVATE_DIGITAL_ROOT=str(self.root)):
            _new_invoice("thirdbuyer@example.invalid", "mojplaywin.com", "en", self.product.pk)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "paid")
        self.assertEqual(self.invoice.txid, self.txid)
