"""Persistent Signal Desk terms use the real merchant receipt contract."""
import hashlib
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.crown_tron_receipts import PROVIDER
from core.models import Product, Order, OrderItem, PaymentIntent, PaymentWebhookEvent, LedgerEntry
from mpw_commerce.models import CommerceFulfillment
from mpw_commerce.signal_subscriptions import (
    snapshot_subscription, subscription_access, SubscriptionRejected,
)
from services.mojtaba_tron_owner_receiver import APPROVED_NATIVE_TRX_RECIPIENT


class SignalSubscriptionTests(TestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user(username="signal_sub_buyer")
        self.other = get_user_model().objects.create_user(username="signal_sub_other")
        self.product = Product.objects.create(
            title="Monthly educational research", product_type="subscription",
            price=Decimal("29.90"), currency="USD", active=True,
            metadata={"signal_plan_id": "education-monthly", "rights_cleared": True,
                      "mpw_commerce": {"enabled": True, "fulfillment": "subscription"}},
        )
        self.order = Order.objects.create(customer=self.buyer, total=self.product.price,
                                          currency="USD", status="pending")
        self.item = OrderItem.objects.create(order=self.order, product=self.product,
                                             quantity=1, unit_price=self.product.price,
                                             currency="USD")

    def test_terms_snapshot_is_idempotent_and_unpaid_access_denied(self):
        sub = snapshot_subscription(self.item.pk)
        self.assertEqual(sub.term_weeks, 4)
        self.assertEqual(snapshot_subscription(self.item.pk).pk, sub.pk)
        self.assertIsNone(subscription_access(self.buyer, self.item.pk))

    def test_digital_product_never_becomes_subscription(self):
        self.product.product_type = "digital"
        self.product.save(update_fields=["product_type"])
        with self.assertRaises(SubscriptionRejected):
            snapshot_subscription(self.item.pk)

    def test_real_receipt_contract_expiry_buyer_and_refund(self):
        snapshot_subscription(self.item.pk)
        receiver = APPROVED_NATIVE_TRX_RECIPIENT
        sun = 123456789
        intent = PaymentIntent.objects.create(
            order=self.order, amount=self.order.total, currency="USD", status="paid",
            provider=PROVIDER, idempotency_key="wltrx1:" +
            hashlib.sha256(receiver.encode("ascii")).hexdigest() + ":" + str(sun),
            provider_reference=json.dumps({"v": 1, "to": receiver, "sun": sun,
                                           "rate": "0.25", "at": timezone.now().isoformat()}),
        )
        event = PaymentWebhookEvent.objects.create(
            payment_intent=intent, provider=PROVIDER, event_type="tron_finalized",
            event_id="a" * 64, payload_hash="b" * 64, status="processed",
        )
        LedgerEntry.objects.create(
            order=self.order, payment_intent=intent, entry_type="credit",
            amount=self.order.total, currency="USD",
            reference="walletless:tron-mainnet:" + event.event_id,
            metadata={"payment_method": PROVIDER, "network": "tron-mainnet",
                      "tx_hash": event.event_id, "evidence_digest": event.payload_hash,
                      "sender": receiver, "walletless_receipt_event_id": event.pk},
        )
        self.order.status = "paid"
        self.order.save(update_fields=["status"])
        CommerceFulfillment.objects.create(item=self.item, kind="subscription", status="queued")
        access = subscription_access(self.buyer, self.item.pk)
        self.assertEqual(access["current_week"], 1)
        self.assertIsNone(subscription_access(self.other, self.item.pk))
        self.assertIsNone(subscription_access(self.buyer, self.item.pk,
                                              now=event.created_at + timedelta(weeks=4)))
        LedgerEntry.objects.create(order=self.order, payment_intent=intent,
                                   entry_type="refund", amount=Decimal("1.00"),
                                   currency="USD", reference="signal-test-refund")
        self.assertIsNone(subscription_access(self.buyer, self.item.pk))
