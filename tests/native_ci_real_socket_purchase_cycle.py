"""Real Django+Unix-socket loopback integration, fake chain evidence only.

Checks the unmodified Core Order/OrderItem models, durable outbox, on_commit
notifications, PRIVATE on-host HMAC receiver, read-only per-asset wakeup,
independent blockchain validation gate, order ledger and download entitlement.

NO public URL, real coins, merchant wallet signatures, production DB or
OpenAI requests. Test approval metadata is fake and confined to in-memory DB.
"""
import os
from pathlib import Path
import tempfile
import threading
import time
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import LedgerEntry, Order, OrderItem, Product
from mpw_native_checkout.entitlements import can_download_paid_native_order
from mpw_native_checkout.models import NativeInvoice, NativeWatchOutbox
from mpw_native_checkout.settlement import settle_native_invoice, SettlementRejected
from scripts.mojplaywin_cpanel_local_event_worker import (
    run_local_worker, SOCKET_BASENAME,
)

KEY = b"staging-complete-cycle-only-not-a-real-wallet-key-" * 2
ETH_RECEIVER = "0x89149b01f59115B86553561F12438D2ADF517E75"
ETH_SENDER = "0x" + "a" * 40
TX = "0x" + "d" * 64


class EventDrivenDjangoCycleTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.private = Path(self.temp.name) / "private"
        self.private.mkdir(mode=0o700)
        self.secret_file = self.private / "hmac"
        self.secret_file.write_bytes(KEY)
        self.secret_file.chmod(0o600)
        self.now = timezone.now()
        self.user = get_user_model().objects.create_user(
            username="ci-complete-cycle-buyer", password="unused-test-password",
        )
        self.product = Product.objects.create(
            pk=72, title="The Science and Practice of Chess Improvement",
            product_type="digital_book", active=True, currency="USD",
            price=Decimal("7.50"),
            metadata={
                "product_id":"mojplaywin-chess-improvement-2026",
                "asset_verified":True, "payment_live":True,
            },
        )
        self.order = Order.objects.create(
            customer=self.user, total=Decimal("7.50"),
            status="pending", currency="USD",
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, quantity=1,
            currency="USD", unit_price=Decimal("7.50"),
        )
        self.scan_calls = []
        self.worker_errors = []
        self.worker_thread = None

    def start_listener(self):
        def eth_indexer():
            self.scan_calls.append("ETH")
            return []  # deliberately no fake payment settlement by indexer
        def trx_indexer():
            raise AssertionError("Unexpected TRX scan for ETH-only order")
        def worker():
            try:
                run_local_worker(
                    self.private, KEY, eth_scan=eth_indexer,
                    trx_scan=trx_indexer, stop_after_events=2,
                )
            except Exception as exc:
                self.worker_errors.append(type(exc).__name__)
        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()
        end = time.monotonic() + 4
        while time.monotonic() < end:
            if (self.private / SOCKET_BASENAME).exists():
                break
            time.sleep(0.02)
        self.assertTrue((self.private / SOCKET_BASENAME).exists())

    def create_verified_fixture(self):
        # These time fields simulate approvals. No real signature or wallet
        # control is proven by these tests, so NEVER enable this in production.
        with self.captureOnCommitCallbacks(execute=True):
            invoice = NativeInvoice.objects.create(
                order=self.order, product=self.product, customer=self.user,
                asset="ETH", network="ethereum-mainnet",
                merchant_address=ETH_RECEIVER,
                verified_sender_address=ETH_SENDER,
                amount_atomic="2500000000000000",
                usd_amount=Decimal("7.50"), usd_per_asset=Decimal("3000"),
                price_source="coingecko",
                price_observed_at=self.now-timedelta(seconds=20),
                issued_at=self.now, expires_at=self.now+timedelta(minutes=10),
                wallet_challenge_id="ci-only-no-real-wallet-proof",
                sender_signature_verified_at=self.now,
                merchant_ownership_verified_at=None,
            )
        return invoice

    def await_scan(self):
        deadline=time.monotonic()+4
        while time.monotonic()<deadline and len(self.scan_calls)<1:
            time.sleep(.01)
        self.assertEqual(self.scan_calls,["ETH"])

    def assert_listener_closed(self):
        self.worker_thread.join(timeout=5)
        self.assertFalse(self.worker_thread.is_alive())
        self.assertEqual(self.worker_errors,[])
        self.assertFalse((self.private/"pending-orders.mode").exists())

    def stop_invoice(self, invoice, status):
        with self.captureOnCommitCallbacks(execute=True):
            invoice.status=status
            invoice.save(update_fields=["status","updated_at"])
        self.assert_listener_closed()

    def event_settings(self):
        return override_settings(
            MPW_NATIVE_EVENT_ENABLED=True,
            MPW_NATIVE_EVENT_TRANSPORT="unix",
            MPW_NATIVE_EVENT_SOCKET=str(self.private/SOCKET_BASENAME),
            MPW_NATIVE_EVENT_SECRET_FILE=str(self.secret_file),
            MPW_NATIVE_EVENT_SECRET="",
        )

    def test_native_verified_receipt_unlocks_real_django_order_after_event(self):
        with self.event_settings():
            self.start_listener()
            self.assertEqual(self.scan_calls,[])
            invoice=self.create_verified_fixture()
            self.await_scan()
            self.assertEqual(
                NativeWatchOutbox.objects.get(invoice=invoice).state,"delivered"
            )
            self.assertFalse(can_download_paid_native_order(self.order.pk,self.user.pk))
            self.assertFalse(LedgerEntry.objects.filter(order=self.order).exists())
            proof={
                "network":invoice.network, "order_id":invoice.order_id,
                "transaction_hash":TX,
                "amount_smallest_units":int(invoice.amount_atomic),
                "sender":ETH_SENDER.lower(), "recipient":ETH_RECEIVER.lower(),
            }
            # Mocked verified receipt; no real payment or RPC call.
            with patch(
                "mpw_native_checkout.settlement.verify_eth_transfer",
                return_value=proof,
            ), self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(
                    settle_native_invoice(invoice.pk, TX, ethereum_rpc=lambda *args:{}),
                    "paid",
                )
            self.assert_listener_closed()  # paid settlement already sent close
            self.assertEqual(self.scan_calls,["ETH"])  # close never polls
            self.order.refresh_from_db()
            self.assertEqual(self.order.status,"paid")
            self.assertEqual(LedgerEntry.objects.filter(order=self.order).count(),1)
            self.assertTrue(can_download_paid_native_order(self.order.pk,self.user.pk))

    def test_purchase_event_without_verified_chain_does_not_unlock_book(self):
        with self.event_settings():
            self.start_listener()
            invoice=self.create_verified_fixture()
            self.assertEqual(self.scan_calls,["ETH"])
            with self.assertRaises(SettlementRejected):
                settle_native_invoice(invoice.pk,TX,ethereum_rpc=None)
            self.assertEqual(self.order.status,"pending")
            self.assertFalse(can_download_paid_native_order(self.order.pk,self.user.pk))
            self.assertFalse(LedgerEntry.objects.filter(order=self.order).exists())
            self.stop_invoice(invoice,NativeInvoice.Status.EXPIRED)
            self.assertEqual(self.scan_calls,["ETH"])
