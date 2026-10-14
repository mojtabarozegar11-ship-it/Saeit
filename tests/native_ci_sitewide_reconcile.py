"""Offline checks for the independent read-only payment watcher.

Candidate discovery never counts as a payment by itself. The only settlement
call is the independently verified internal ledger transaction.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock,patch
from io import StringIO
from django.core.management import call_command

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Order
from mpw_commerce.models import CommerceInvoice
from mpw_commerce.auto_reconcile import (
    reconcile_pending_orders, ReconciliationUnavailable,
)
from scripts.mojplaywin_direct_wallet_discovery import Candidate,IndexerUnavailable

ETH="0x89149b01f59115B86553561F12438D2ADF517E75"
TRX="THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
SENDER="0x"+"c"*40
HASH="0x"+"a"*64
FLAGS={
    "MPW_COMMERCE_RELEASE_READY":True,
    "MPW_COMMERCE_AUTORECONCILE_ENABLED":True,
    "MPW_COMMERCE_SETTLEMENT_ENABLED":True,
    "MPW_COMMERCE_REAL_RPC_ENABLED":True,
}


class ReconciliationTests(TestCase):
    def setUp(self):
        self.now=timezone.now()
        buyer=get_user_model().objects.create_user(username="pending-order-buyer")
        self.order=Order.objects.create(
            customer=buyer,status="pending",total=Decimal("21.00"),currency="USD",
        )

    def invoice(self,asset="ETH",offset=0):
        return CommerceInvoice.objects.create(
            order=self.order,asset=asset,
            network="ethereum-mainnet" if asset=="ETH" else "tron-mainnet",
            recipient=ETH if asset=="ETH" else TRX,
            expected_sender=SENDER if asset=="ETH" else TRX,
            amount_atomic=str(1000000000000+offset),
            total_usd=Decimal("21.00"),quote_usd_per_asset=Decimal("3000.00"),
            quote_source="coingecko",quote_observed_at=self.now,
            sender_challenge_id="sender-proof-id",
            sender_signature_verified_at=self.now,
            issued_at=self.now,expires_at=self.now+timedelta(minutes=10),
        )

    def eth_candidate(self,invoice):
        return Candidate(
            "ethereum-mainnet",HASH,SENDER.lower(),ETH.lower(),
            invoice.amount_atomic,int(self.now.timestamp()*1000),
        )

    def test_release_disabled_does_not_discover_or_settle(self):
        eth=Mock(side_effect=AssertionError("No chain calls"))
        settle=Mock(side_effect=AssertionError("No settlement"))
        with override_settings(MPW_COMMERCE_AUTORECONCILE_ENABLED=False):
            result=reconcile_pending_orders(
                now=self.now,eth_scanner=eth,settler=settle
            )
        self.assertEqual(result["state"],"disabled")
        eth.assert_not_called()
        settle.assert_not_called()

    def test_release_not_ready_disables_all_chain_checks_even_with_other_flags_on(self):
        eth=Mock(side_effect=AssertionError("No network while not released"))
        with override_settings(**{**FLAGS,"MPW_COMMERCE_RELEASE_READY":False}):
            result=reconcile_pending_orders(now=self.now,eth_scanner=eth)
        self.assertEqual(result["state"],"disabled")
        eth.assert_not_called()

    def test_management_command_off_never_initiates_payment_check(self):
        output=StringIO()
        with override_settings(MPW_COMMERCE_RELEASE_READY=False):
            call_command("mpw_commerce_reconcile",stdout=output)
        self.assertIn("state=disabled",output.getvalue())
        self.assertIn("paid=0",output.getvalue())

    @override_settings(**FLAGS)
    def test_idle_has_zero_chain_requests(self):
        eth=Mock(side_effect=AssertionError("No chain calls"))
        trx=Mock(side_effect=AssertionError("No chain calls"))
        result=reconcile_pending_orders(
            now=self.now,eth_scanner=eth,trx_scanner=trx
        )
        self.assertEqual(result["state"],"idle")
        eth.assert_not_called()
        trx.assert_not_called()

    @override_settings(**FLAGS)
    def test_only_eth_candidates_reach_trusted_settlement(self):
        inv=self.invoice()
        eth=Mock(return_value=[self.eth_candidate(inv)])
        trx=Mock(side_effect=AssertionError("Wrong network queried"))
        verifier=Mock()
        settler=Mock(return_value="paid")
        result=reconcile_pending_orders(
            asset_filter="ETH",now=self.now,eth_scanner=eth,
            trx_scanner=trx,verifier=verifier,settler=settler
        )
        self.assertEqual(result["state"],"scanned")
        self.assertEqual(result["matched"],1)
        self.assertEqual(result["paid"],1)
        self.assertEqual(settler.call_args.args,(inv.pk,HASH))
        self.assertIs(settler.call_args.kwargs["trusted_chain_verifier"],verifier)
        trx.assert_not_called()
        self.assertEqual(eth.call_count,1)

    @override_settings(**FLAGS)
    def test_wrong_recipient_cannot_match(self):
        inv=self.invoice()
        bad=Candidate(
            "ethereum-mainnet",HASH,SENDER.lower(),"0x"+"e"*40,
            inv.amount_atomic,int(self.now.timestamp()*1000)
        )
        settler=Mock(side_effect=AssertionError("No settlement"))
        result=reconcile_pending_orders(
            now=self.now,eth_scanner=lambda **_: [bad],settler=settler
        )
        self.assertEqual(result["matched"],0)
        settler.assert_not_called()

    @override_settings(**FLAGS)
    def test_indexer_failure_never_approves_order(self):
        self.invoice()
        settler=Mock(side_effect=AssertionError("No settlement"))
        def unavailable(**kwargs):
            raise IndexerUnavailable("Read-only indexer offline")
        with self.assertRaises(ReconciliationUnavailable):
            reconcile_pending_orders(
                now=self.now,eth_scanner=unavailable,settler=settler
            )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,"pending")
        settler.assert_not_called()

    @override_settings(**FLAGS)
    def test_stale_invoice_outside_bounded_scan_window(self):
        inv=self.invoice()
        inv.issued_at=self.now-timedelta(days=2)
        inv.save(update_fields=["issued_at"])
        eth=Mock(side_effect=AssertionError("No scan"))
        result=reconcile_pending_orders(now=self.now,eth_scanner=eth)
        self.assertEqual(result["state"],"idle")
        eth.assert_not_called()

    @override_settings(**FLAGS)
    def test_database_uniqueness_conflict_never_marks_order_paid(self):
        invoice=self.invoice()
        settlement=Mock(side_effect=IntegrityError("duplicate on-chain tx"))
        result=reconcile_pending_orders(
            now=self.now,
            eth_scanner=lambda **_: [self.eth_candidate(invoice)],
            settler=settlement,
        )
        self.assertEqual(result["matched"],1)
        self.assertEqual(result["paid"],0)
        self.assertEqual(result["rejected"],1)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,"pending")

    @override_settings(**FLAGS)
    def test_more_than_one_batch_never_silently_skips_invoices(self):
        buyer=self.order.customer
        orders=Order.objects.bulk_create([
            Order(customer=buyer,status="pending",total=Decimal("21.00"),
                  currency="USD")
            for _ in range(101)
        ])
        CommerceInvoice.objects.bulk_create([
            CommerceInvoice(
                order=o,asset="ETH",network="ethereum-mainnet",
                recipient=ETH,expected_sender=SENDER,
                amount_atomic=str(1000000000000+i),
                total_usd=Decimal("21.00"),
                quote_usd_per_asset=Decimal("3000"),
                quote_source="coingecko",quote_observed_at=self.now,
                sender_challenge_id="sample-challenge",
                sender_signature_verified_at=self.now,
                issued_at=self.now,expires_at=self.now+timedelta(minutes=10),
            ) for i,o in enumerate(orders)
        ])
        eth_scanner=Mock(side_effect=AssertionError("Do not skip overflow silently"))
        with self.assertRaises(ReconciliationUnavailable):
            reconcile_pending_orders(now=self.now,eth_scanner=eth_scanner)
        eth_scanner.assert_not_called()

    @override_settings(**FLAGS)
    def test_invalid_asset_filter_rejected_before_chain_network(self):
        eth=Mock(side_effect=AssertionError("No chain calls"))
        with self.assertRaises(ReconciliationUnavailable):
            reconcile_pending_orders(asset_filter="USDT",eth_scanner=eth)
        eth.assert_not_called()
