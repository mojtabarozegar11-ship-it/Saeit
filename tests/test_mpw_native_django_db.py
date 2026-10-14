"""Isolated Django schema integration tests. Never connect to production."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from core.models import Order, Product
from mpw_native_checkout.models import NativeInvoice, NativeChainTransfer


class NativeInvoiceDatabaseTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ci-invoice-buyer", password="not-a-real-password")
        self.product = Product.objects.create(
            title="The Science and Practice of Chess Improvement",
            product_type="digital_book", currency="USD",
            price=Decimal("7.50"), active=False,
        )
        self.now = timezone.now()

    def order(self):
        return Order.objects.create(customer=self.user, total=Decimal("7.50"),
                                    currency="USD", status="pending")

    def invoice(self, order=None, amount=25000000):
        return NativeInvoice.objects.create(
            order=order or self.order(), product=self.product, customer=self.user,
            asset="TRX", network="tron-mainnet",
            merchant_address="THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73",
            verified_sender_address="TMadeUpSenderForSchemaTestsOnly",
            amount_atomic=Decimal(amount),
            usd_amount=Decimal("7.50"), usd_per_asset=Decimal("0.300000000000"),
            price_source="coingecko",
            price_observed_at=self.now,
            issued_at=self.now, expires_at=self.now + timedelta(minutes=10),
            wallet_challenge_id="signed-challenge-1",
            sender_signature_verified_at=self.now,
            merchant_ownership_verified_at=self.now,
        )

    def transfer(self, invoice, digest):
        return NativeChainTransfer.objects.create(
            invoice=invoice, network="tron-mainnet", tx_hash=digest,
            sender_address="TMadeUpSenderForSchemaTestsOnly",
            recipient_address="THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73",
            amount_atomic=invoice.amount_atomic, verified_at=self.now,
            verification_backend="ci-simulation", evidence_digest="1"*64,
        )

    def test_invoice_persists(self):
        a=self.invoice()
        a.refresh_from_db()
        self.assertEqual(a.order.status, "pending")
        self.assertEqual(a.status, "awaiting")
        self.assertEqual(a.usd_amount, Decimal("7.50"))

    def test_same_chain_amount_cannot_be_reassigned(self):
        self.invoice()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.invoice(amount=25000000)
        self.assertEqual(NativeInvoice.objects.count(),1)

    def test_distinct_amount_allowed_in_staging(self):
        self.invoice()
        self.invoice(amount=25000001)
        self.assertEqual(NativeInvoice.objects.count(),2)

    def test_one_chain_hash_cannot_settle_two_invoices(self):
        one=self.invoice()
        two=self.invoice(amount=25000001)
        digest="a"*64
        self.transfer(one,digest)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.transfer(two,digest)
        self.assertEqual(NativeChainTransfer.objects.count(),1)

    def test_positive_amount_is_enforced(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.invoice(amount=0)
        self.assertFalse(NativeInvoice.objects.exists())

    def test_no_live_order_is_implicitly_paid_by_chain_receipt(self):
        invoice=self.invoice()
        self.transfer(invoice,"a"*64)
        invoice.order.refresh_from_db()
        self.assertEqual(invoice.order.status,"pending")
        self.assertFalse(invoice.product.active)
