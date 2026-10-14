"""Unattended payment worker tests, with ALL external indexers and RPCs mocked."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.utils import timezone

from core.models import Order, OrderItem, Product, LedgerEntry
from mpw_native_checkout.entitlements import can_download_paid_native_order
from mpw_native_checkout.models import NativeInvoice
from mpw_native_checkout.autopay_worker import reconcile_once, AutoPayUnavailable
from scripts.mojplaywin_direct_wallet_discovery import Candidate, IndexerUnavailable
from scripts.mojplaywin_native_chain_verify import tron_address_to_hex

ETH_WALLET="0x89149b01f59115B86553561F12438D2ADF517E75"
TRX_WALLET="THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
ETH_SENDER="0x"+"a"*40
ETH_TX="0x"+"b"*64
TRX_TX="c"*64
ON={"MPW_NATIVE_AUTOPAY_ENABLED":True,
    "MPW_NATIVE_MERCHANT_PROOFS":{"ETH":True,"TRX":True}}


class AutoPayWorkerTests(TestCase):
    def setUp(self):
        self.now=timezone.now()
        self.owner=get_user_model().objects.create_user(
            username="automatic-worker-buyer",password="test-only",
        )
        self.product=Product.objects.create(
            pk=72,title="The Science and Practice of Chess Improvement",
            product_type="ebook_pdf",price=Decimal("7.50"),currency="USD",
            active=True,metadata={
                "product_id":"mojplaywin-chess-improvement-2026",
                "asset_verified":True,"payment_live":True,
            },
        )

    def new_invoice(self,asset="ETH",days_ago=0):
        order=Order.objects.create(
            customer=self.owner,total=Decimal("7.50"),
            currency="USD",status="pending",
        )
        OrderItem.objects.create(
            order=order,product=self.product,quantity=1,
            unit_price=Decimal("7.50"),currency="USD",
        )
        return NativeInvoice.objects.create(
            order=order,customer=self.owner,product=self.product,
            asset=asset,network="ethereum-mainnet" if asset=="ETH" else "tron-mainnet",
            merchant_address=ETH_WALLET if asset=="ETH" else TRX_WALLET,
            verified_sender_address=ETH_SENDER if asset=="ETH" else TRX_WALLET,
            amount_atomic="2500000000000000" if asset=="ETH" else "25000000",
            usd_amount=Decimal("7.50"),
            usd_per_asset=Decimal("3000" if asset=="ETH" else "0.30"),
            price_source="coingecko",
            price_observed_at=self.now-timedelta(seconds=20),
            issued_at=self.now-timedelta(days=days_ago),
            expires_at=self.now-timedelta(days=days_ago)+timedelta(minutes=10),
            wallet_challenge_id="test-wallet-proof",
            sender_signature_verified_at=self.now,
            merchant_ownership_verified_at=self.now,
        )

    def eth_candidate(self,sender=ETH_SENDER):
        return Candidate("ethereum-mainnet",ETH_TX,sender.lower(),
                        ETH_WALLET.lower(),"2500000000000000",
                        int(self.now.timestamp()*1000)-20000)

    def tron_candidate(self):
        trx_hex=tron_address_to_hex(TRX_WALLET).lower()
        return Candidate("tron-mainnet",TRX_TX,trx_hex,trx_hex,
                        "25000000",int(self.now.timestamp()*1000)-20000)

    def test_feature_flag_defaults_off(self):
        invoice=self.new_invoice()
        with override_settings(MPW_NATIVE_AUTOPAY_ENABLED=False):
            with patch("mpw_native_checkout.autopay_worker.settle_native_invoice") as settlement:
                result=reconcile_once(now=self.now)
        self.assertEqual(result["state"],"disabled")
        settlement.assert_not_called()

    def test_merchant_proof_is_mandatory(self):
        self.new_invoice()
        with override_settings(MPW_NATIVE_AUTOPAY_ENABLED=True,MPW_NATIVE_MERCHANT_PROOFS={}):
            with self.assertRaises(AutoPayUnavailable):
                reconcile_once(now=self.now)

    @override_settings(**ON)
    def test_no_invoices_skip_network(self):
        with patch("mpw_native_checkout.autopay_worker.discover_eth") as get_eth:
            result=reconcile_once(now=self.now,eth_scanner=get_eth)
        self.assertEqual(result["state"],"no_pending")
        get_eth.assert_not_called()

    @override_settings(**ON)
    def test_matching_eth_transfer_queued_for_trusted_settlement(self):
        invoice=self.new_invoice()
        candidate=self.eth_candidate()
        with patch("mpw_native_checkout.autopay_worker.settle_native_invoice",return_value="paid") as settlement:
            result=reconcile_once(
                now=self.now,eth_scanner=lambda **opts:[candidate],
                trx_scanner=lambda **opts:[],
            )
        self.assertEqual(result["matched"],1)
        self.assertEqual(result["paid"],1)
        self.assertEqual(settlement.call_args.args,(invoice.pk,ETH_TX))

    @override_settings(**ON)
    def test_matching_tron_base58_invoice_is_found_from_hex41_index(self):
        invoice=self.new_invoice(asset="TRX")
        candidate=self.tron_candidate()
        with patch("mpw_native_checkout.autopay_worker.settle_native_invoice",return_value="paid") as settlement:
            result=reconcile_once(
                now=self.now,eth_scanner=lambda **opts:[],
                trx_scanner=lambda **opts:[candidate],
            )
        self.assertEqual(result["matched"],1)
        self.assertEqual(settlement.call_args.args,(invoice.pk,TRX_TX))

    @override_settings(**ON)
    def test_wrong_sender_never_credited(self):
        invoice=self.new_invoice()
        with patch("mpw_native_checkout.autopay_worker.settle_native_invoice") as settlement:
            result=reconcile_once(now=self.now,
                eth_scanner=lambda **opts:[self.eth_candidate("0x"+"e"*40)])
        self.assertEqual(result["matched"],0)
        settlement.assert_not_called()

    @override_settings(**ON)
    def test_unavailable_indexer_fails_closed(self):
        invoice=self.new_invoice()
        def fails(**opts):
            raise IndexerUnavailable("indexer offline")
        with patch("mpw_native_checkout.autopay_worker.settle_native_invoice") as settlement:
            with self.assertRaises(AutoPayUnavailable):
                reconcile_once(now=self.now,eth_scanner=fails)
        settlement.assert_not_called()

    @override_settings(**ON)
    def test_old_invoice_requires_manual_reconciliation(self):
        self.new_invoice(days_ago=2)
        with patch("mpw_native_checkout.autopay_worker.settle_native_invoice") as settlement:
            result=reconcile_once(now=self.now,eth_scanner=lambda **opts:[self.eth_candidate()])
        self.assertEqual(result["state"],"no_pending")
        settlement.assert_not_called()

    @override_settings(**ON)
    def test_duplicate_indexed_transaction_is_matched_once(self):
        self.new_invoice()
        candidate=self.eth_candidate()
        with patch("mpw_native_checkout.autopay_worker.settle_native_invoice",return_value="paid") as settlement:
            result=reconcile_once(now=self.now,eth_scanner=lambda **opts:[candidate,candidate])
        self.assertEqual(result["matched"],1)
        self.assertEqual(settlement.call_count,1)

    @override_settings(**ON)
    def test_invalid_chain_receipt_does_not_credit(self):
        invoice=self.new_invoice()
        with patch("mpw_native_checkout.autopay_worker.settle_native_invoice",
                   side_effect=ValueError("Proof rejected")):
            result=reconcile_once(now=self.now,eth_scanner=lambda **opts:[self.eth_candidate()])
        self.assertEqual(result["paid"],0)
        self.assertEqual(result["rejected"],1)
        invoice.order.refresh_from_db()
        self.assertEqual(invoice.order.status,"pending")




    @override_settings(MPW_NATIVE_AUTOPAY_ENABLED=False)
    def test_scheduled_command_wont_credit_when_disabled(self):
        sink=StringIO()
        call_command("mpw_native_autopay",stdout=sink)
        self.assertIn("NO_PAID_STATE_CHANGES_FEATURE_FLAG_DISABLED",sink.getvalue())

    @override_settings(**ON)
    def test_full_eth_worker_to_django_order_and_download_entitlement(self):
        invoice=self.new_invoice()
        candidate=self.eth_candidate()
        proof={
            "network":"ethereum-mainnet","order_id":invoice.order_id,
            "transaction_hash":ETH_TX,"amount_smallest_units":int(invoice.amount_atomic),
            "sender":invoice.verified_sender_address.lower(),
            "recipient":invoice.merchant_address.lower(),
        }
        with patch("mpw_native_checkout.settlement.verify_eth_transfer",return_value=proof):
            result=reconcile_once(
                now=self.now,eth_scanner=lambda **opts:[candidate],
                eth_chain_rpc=lambda *args:{},
            )
        invoice.order.refresh_from_db()
        self.assertEqual(result["paid"],1)
        self.assertEqual(invoice.order.status,"paid")
        self.assertEqual(LedgerEntry.objects.filter(order=invoice.order).count(),1)
        self.assertTrue(can_download_paid_native_order(invoice.order_id,self.owner.pk))

    @override_settings(**ON)
    def test_full_trx_worker_to_django_order_and_download_entitlement(self):
        invoice=self.new_invoice(asset="TRX")
        candidate=self.tron_candidate()
        proof={
            "network":"tron-mainnet","order_id":invoice.order_id,
            "transaction_hash":TRX_TX,"amount_smallest_units":int(invoice.amount_atomic),
            "sender":invoice.verified_sender_address,
            "recipient":invoice.merchant_address,
        }
        with patch("mpw_native_checkout.settlement.verify_trx_transfer",return_value=proof):
            result=reconcile_once(
                now=self.now,trx_scanner=lambda **opts:[candidate],
                trx_chain_rpc=lambda *args:{},
            )
        invoice.order.refresh_from_db()
        self.assertEqual(result["paid"],1)
        self.assertEqual(invoice.order.status,"paid")
        self.assertEqual(LedgerEntry.objects.filter(order=invoice.order).count(),1)
        self.assertTrue(can_download_paid_native_order(invoice.order_id,self.owner.pk))
