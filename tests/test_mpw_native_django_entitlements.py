"""Staging-only Django entitlement integration tests with fabricated chain evidence."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import Order, OrderItem, Product
from mpw_native_checkout.models import NativeInvoice, NativeChainTransfer
from mpw_native_checkout.entitlements import qualified_order, can_download_paid_native_order


class NativeEntitlementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="native-entitle-buyer",password="test-password")
        self.now = timezone.now()
        self.product = Product.objects.create(
            id=72,
            title="The Science and Practice of Chess Improvement",
            product_type="digital_book", currency="USD", price=Decimal("7.50"),
            active=False,
            metadata={"product_id":"mojplaywin-chess-improvement-2026",
                      "asset_verified":True,"payment_live":False},
        )
        self.order = Order.objects.create(
            customer=self.user,status="pending",currency="USD",total=Decimal("7.50"))
        self.item = OrderItem.objects.create(
            order=self.order,product=self.product,quantity=1,
            unit_price=Decimal("7.50"),currency="USD",
        )
        self.invoice = NativeInvoice.objects.create(
            order=self.order,product=self.product,customer=self.user,asset="ETH",
            network="ethereum-mainnet",
            merchant_address="0x89149b01f59115B86553561F12438D2ADF517E75",
            verified_sender_address="0x"+"a"*40,
            amount_atomic=Decimal("2500000000000000"),
            usd_amount=Decimal("7.50"),usd_per_asset=Decimal("3000"),
            price_source="coingecko",price_observed_at=self.now,
            issued_at=self.now,expires_at=self.now+timedelta(minutes=10),
            wallet_challenge_id="test-signed-challenge",
            sender_signature_verified_at=self.now,
            merchant_ownership_verified_at=self.now,
        )

    def activate_for_test(self):
        self.product.active=True
        data=dict(self.product.metadata)
        data["payment_live"]=True
        self.product.metadata=data
        self.product.save(update_fields=["active","metadata","updated_at"])

    def create_evidence(self,backend="verified-ethereum-mainnet-rpc"):
        return NativeChainTransfer.objects.create(
            invoice=self.invoice,network=self.invoice.network,
            tx_hash="0x"+"c"*64,
            sender_address=self.invoice.verified_sender_address,
            recipient_address=self.invoice.merchant_address,
            amount_atomic=self.invoice.amount_atomic,
            verified_at=self.now,
            verification_backend=backend,
            evidence_digest="e"*64,
        )

    def make_paid(self):
        self.activate_for_test()
        self.order.status="paid"
        self.order.save(update_fields=["status","updated_at"])
        self.invoice.status=NativeInvoice.Status.PAID
        self.invoice.save(update_fields=["status","updated_at"])

    def test_inactive_product_cannot_checkout(self):
        self.assertFalse(qualified_order(self.order.pk,self.user.pk))

    def test_pending_order_cannot_download(self):
        self.assertFalse(can_download_paid_native_order(self.order.pk,self.user.pk))

    def test_checkout_requires_asset_and_payment_gates(self):
        self.activate_for_test()
        self.assertTrue(qualified_order(self.order.pk,self.user.pk))

    def test_paid_without_transfer_cannot_download(self):
        self.make_paid()
        self.assertFalse(can_download_paid_native_order(self.order.pk,self.user.pk))

    def test_mocked_complete_verified_state_is_eligible(self):
        self.make_paid()
        self.create_evidence()
        self.assertTrue(can_download_paid_native_order(self.order.pk,self.user.pk))

    def test_claimed_paid_by_different_customer_rejected(self):
        self.make_paid()
        self.create_evidence()
        self.assertFalse(can_download_paid_native_order(self.order.pk,self.user.pk+100))

    def test_mock_backend_does_not_unlock(self):
        self.make_paid()
        self.create_evidence(backend="ci-simulation")
        self.assertFalse(can_download_paid_native_order(self.order.pk,self.user.pk))

    def test_wrong_sender_does_not_unlock(self):
        self.make_paid()
        claim=self.create_evidence()
        claim.sender_address="0x"+"d"*40
        claim.save(update_fields=["sender_address"])
        self.assertFalse(can_download_paid_native_order(self.order.pk,self.user.pk))

    def test_no_merchant_ownership_proof_blocks_download(self):
        self.make_paid()
        self.create_evidence()
        self.invoice.merchant_ownership_verified_at=None
        self.invoice.save(update_fields=["merchant_ownership_verified_at"])
        self.assertFalse(can_download_paid_native_order(self.order.pk,self.user.pk))

    def test_no_product_payment_gate_blocks_download(self):
        self.make_paid()
        self.create_evidence()
        meta=dict(self.product.metadata)
        meta["payment_live"]=False
        self.product.metadata=meta
        self.product.save(update_fields=["metadata","updated_at"])
        self.assertFalse(can_download_paid_native_order(self.order.pk,self.user.pk))

    def test_mismatched_receipt_amount_blocks_download(self):
        self.make_paid()
        claim=self.create_evidence()
        claim.amount_atomic=claim.amount_atomic+1
        claim.save(update_fields=["amount_atomic"])
        self.assertFalse(can_download_paid_native_order(self.order.pk,self.user.pk))
