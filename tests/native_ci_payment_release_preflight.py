"""Isolated release-blocker regressions: NO real wallet or chain operations.

This suite does not establish real mainnet settlement; it must remain separate
from live deployment and only asserts fail-closed staging behavior.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Order, LedgerEntry
from mpw_commerce.models import CommerceInvoice, CommerceReceipt, CommerceFulfillment
from mpw_commerce.auto_reconcile import reconcile_pending_orders
from mpw_commerce.trusted_chain import verify_with_trusted_rpc, ChainAdapterUnavailable
from scripts.mojplaywin_direct_wallet_discovery import Candidate, tron_address_to_hex

GATES = {
    "MPW_COMMERCE_RELEASE_READY": True,
    "MPW_COMMERCE_AUTORECONCILE_ENABLED": True,
    "MPW_COMMERCE_SETTLEMENT_ENABLED": True,
    "MPW_COMMERCE_REAL_RPC_ENABLED": True,
}
ETH_RECEIVER = "0x89149b01f59115B86553561F12438D2ADF517E75"
TRX_RECEIVER = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"


class PaymentReleasePreflightTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        buyer = get_user_model().objects.create_user(username="preflight-buyer")
        self.order = Order.objects.create(
            customer=buyer, status="pending",
            total=Decimal("17.00"), currency="USD",
        )

    def invoice(self, asset):
        receiver = ETH_RECEIVER if asset == "ETH" else TRX_RECEIVER
        return CommerceInvoice.objects.create(
            order=self.order, asset=asset,
            network="ethereum-mainnet" if asset == "ETH" else "tron-mainnet",
            recipient=receiver,
            expected_sender=("0x" + "c" * 40) if asset == "ETH" else TRX_RECEIVER,
            amount_atomic="1100000000000" if asset == "ETH" else "1100000",
            total_usd=Decimal("17.00"), quote_usd_per_asset=Decimal("3000.00"),
            quote_source="ci-fixture", quote_observed_at=self.now,
            sender_challenge_id="signed-fixture",
            sender_signature_verified_at=self.now,
            issued_at=self.now, expires_at=self.now + timedelta(minutes=10),
        )

    def assert_no_sale(self):
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "pending")
        self.assertFalse(LedgerEntry.objects.filter(order=self.order).exists())
        self.assertFalse(CommerceReceipt.objects.exists())
        self.assertFalse(CommerceFulfillment.objects.exists())

    @override_settings(**GATES)
    def test_each_release_gate_off_blocks_rpc_and_settlement(self):
        self.invoice("ETH")
        for gate in GATES:
            with self.subTest(gate=gate), override_settings(**{gate: False}):
                eth = Mock(side_effect=AssertionError("Must never query mainnet"))
                tron = Mock(side_effect=AssertionError("Must never query mainnet"))
                settle = Mock(side_effect=AssertionError("Must never settle"))
                result = reconcile_pending_orders(
                    now=self.now, eth_scanner=eth, trx_scanner=tron,
                    settler=settle,
                )
                self.assertEqual(result["state"], "disabled")
                eth.assert_not_called()
                tron.assert_not_called()
                settle.assert_not_called()
                self.assert_no_sale()

    @override_settings(**{**GATES, "MPW_COMMERCE_REAL_RPC_ENABLED": False})
    def test_direct_verifier_never_calls_rpc_when_real_rpc_disabled(self):
        invoice = self.invoice("ETH")
        eth_rpc = Mock(side_effect=AssertionError("No RPC permitted"))
        with self.assertRaises(ChainAdapterUnavailable):
            verify_with_trusted_rpc(invoice, "0x" + "a" * 64, eth_rpc=eth_rpc)
        eth_rpc.assert_not_called()
        self.assert_no_sale()

    @override_settings(**GATES)
    def test_trx_discovery_only_reaches_internal_verified_settler(self):
        invoice = self.invoice("TRX")
        eth = Mock(side_effect=AssertionError("ETH indexer unnecessary"))
        candidate = Candidate(
            "tron-mainnet", "a" * 64,
            tron_address_to_hex(TRX_RECEIVER).lower(),\n            tron_address_to_hex(TRX_RECEIVER).lower(),
            invoice.amount_atomic, int(self.now.timestamp() * 1000),
        )
        tron = Mock(return_value=[candidate])
        verifier = Mock(side_effect=AssertionError("Only pass trusted verifier"))
        settle = Mock(return_value="already_paid")
        result = reconcile_pending_orders(
            now=self.now, eth_scanner=eth, trx_scanner=tron,
            verifier=verifier, settler=settle,
        )
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["paid"], 0)
        eth.assert_not_called()
        tron.assert_called_once()
        settle.assert_called_once_with(
            invoice.pk, "a" * 64, trusted_chain_verifier=verifier,
        )
        verifier.assert_not_called()
        self.assert_no_sale()
