"""Tests: failed purchase messages cannot silently disappear from Django."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Order, OrderItem, Product
from mpw_native_checkout.models import NativeInvoice, NativeWatchOutbox
from mpw_native_checkout.purchase_notify import (
    NotificationUnavailable,
    dispatch_queued_watch_event,
    flush_pending_watch_events,
)

EVENT_ON = {"MPW_NATIVE_EVENT_ENABLED": True}


class DurableWatchOutboxTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.user = get_user_model().objects.create_user(
            username="outbox-buyer", password="unused-in-test",
        )
        self.product = Product.objects.create(
            pk=72, title="The Science and Practice of Chess Improvement",
            product_type="digital_book", price=Decimal("7.50"), currency="USD",
            active=False,
        )
        self.order = Order.objects.create(
            customer=self.user, status="pending", currency="USD", total=Decimal("7.50"),
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, quantity=1,
            unit_price=Decimal("7.50"), currency="USD",
        )
        self.invoice = NativeInvoice.objects.create(
            order=self.order, customer=self.user, product=self.product,
            asset="ETH", network="ethereum-mainnet",
            merchant_address="0x89149b01f59115B86553561F12438D2ADF517E75",
            verified_sender_address="0x" + "b" * 40,
            amount_atomic="2500000000000000",
            usd_amount=Decimal("7.50"), usd_per_asset=Decimal("3000"),
            price_source="coingecko",
            price_observed_at=self.now,
            issued_at=self.now, expires_at=self.now + timedelta(minutes=10),
            wallet_challenge_id="dummy-owned-wallet-proof",
            sender_signature_verified_at=self.now,
            merchant_ownership_verified_at=self.now,
        )

    def test_open_event_persisted_before_remote_delivery(self):
        item = NativeWatchOutbox.objects.get(invoice=self.invoice)
        self.assertEqual(item.action,"invoice_open")
        self.assertEqual(item.state,"pending")

    def test_paid_event_replaces_pending_open_without_out_of_order_delivery(self):
        self.invoice.status=NativeInvoice.Status.PAID
        self.invoice.save(update_fields=["status","updated_at"])
        item=NativeWatchOutbox.objects.get(invoice=self.invoice)
        self.assertEqual(item.action,"invoice_closed")
        self.assertEqual(NativeWatchOutbox.objects.count(),1)

    @override_settings(**EVENT_ON)
    def test_unreachable_event_receiver_keeps_retryable_outbox(self):
        with patch("mpw_native_checkout.purchase_notify.send_invoice_event",
                   side_effect=NotificationUnavailable("offline")):
            result=dispatch_queued_watch_event(self.invoice.pk)
        self.assertEqual(result,"retry_queued")
        item=NativeWatchOutbox.objects.get(invoice=self.invoice)
        self.assertEqual(item.state,"pending")
        self.assertEqual(item.attempts,1)
        self.assertGreater(item.next_attempt_at,timezone.now())

    @override_settings(**EVENT_ON)
    def test_acknowledged_message_completes_outbox(self):
        with patch("mpw_native_checkout.purchase_notify.send_invoice_event",
                   return_value="delivered") as sender:
            result=dispatch_queued_watch_event(self.invoice.pk)
            self.assertEqual(flush_pending_watch_events(limit=20)["attempted"],0)
        item=NativeWatchOutbox.objects.get(invoice=self.invoice)
        self.assertEqual(result,"delivered")
        self.assertEqual(item.state,"delivered")
        self.assertIsNotNone(item.delivered_at)
        sender.assert_called_once()

    @override_settings(MPW_NATIVE_EVENT_ENABLED=False)
    def test_disabled_checkout_outbox_makes_no_network_requests(self):
        with patch("mpw_native_checkout.purchase_notify.send_invoice_event") as sender:
            self.assertEqual(dispatch_queued_watch_event(self.invoice.pk),"disabled")
            self.assertEqual(flush_pending_watch_events(),{"state":"disabled","attempted":0})
        sender.assert_not_called()

    @override_settings(**EVENT_ON)
    def test_backoff_stops_repeated_remote_calls(self):
        with patch("mpw_native_checkout.purchase_notify.send_invoice_event",
                   side_effect=NotificationUnavailable("offline")) as sender:
            dispatch_queued_watch_event(self.invoice.pk)
            result=dispatch_queued_watch_event(self.invoice.pk)
        self.assertEqual(result,"backoff")
        sender.assert_called_once()
