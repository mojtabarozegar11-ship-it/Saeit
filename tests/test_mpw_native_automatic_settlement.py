"""Native Ethereum/TRON automatic Django settlement; all blockchain calls mocked."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import LedgerEntry, Order, OrderItem, Product
from mpw_native_checkout.entitlements import can_download_paid_native_order
from mpw_native_checkout.models import NativeInvoice, NativeChainTransfer
from mpw_native_checkout.settlement import (
    SettlementRejected, settle_native_invoice, reconcile_discovered_transfers,
)

ETH_TX = "0x" + "c" * 64
TRX_TX = "d" * 64
ETH_SENDER = "0x" + "a" * 40
ETH_RECEIVER = "0x89149b01f59115B86553561F12438D2ADF517E75"
TRX_RECEIVER = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"


class NativeAutoSettlementTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.user = get_user_model().objects.create_user(
            username="native-automatic-buyer", password="test-password-only",
        )
        self.book = Product.objects.create(
            pk=72, title="The Science and Practice of Chess Improvement",
            product_type="digital_book", price=Decimal("7.50"), currency="USD",
            active=True, metadata={
                "product_id": "mojplaywin-chess-improvement-2026",
                "asset_verified": True, "payment_live": True,
            }
        )

    def invoice(self, *, asset="ETH", amount=None):
        order = Order.objects.create(
            customer=self.user, status="pending", total=Decimal("7.50"), currency="USD",
        )
        OrderItem.objects.create(
            order=order, product=self.book, quantity=1,
            unit_price=Decimal("7.50"), currency="USD",
        )
        is_eth = asset == "ETH"
        invoice = NativeInvoice.objects.create(
            order=order, product=self.book, customer=self.user,
            asset=asset, network="ethereum-mainnet" if is_eth else "tron-mainnet",
            merchant_address=ETH_RECEIVER if is_eth else TRX_RECEIVER,
            verified_sender_address=ETH_SENDER if is_eth else TRX_RECEIVER,
            amount_atomic=amount or ("2500000000000000" if is_eth else "25000000"),
            usd_amount=Decimal("7.50"), usd_per_asset=Decimal("3000" if is_eth else "0.30"),
            price_source="coingecko",
            price_observed_at=self.now - timedelta(seconds=20),
            issued_at=self.now,
            expires_at=self.now + timedelta(minutes=10),
            wallet_challenge_id="test-signed-challenge",
            sender_signature_verified_at=self.now,
            merchant_ownership_verified_at=self.now,
        )
        return invoice, order

    def expected_proof(self, invoice, tx_hash):
        return {
            "order_id": invoice.order_id,
            "network": invoice.network,
            "transaction_hash": tx_hash,
            "amount_smallest_units": int(invoice.amount_atomic),
            "recipient": invoice.merchant_address,
        }

    def check_unpaid(self, invoice, order):
        invoice.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(invoice.status, "awaiting")
        self.assertEqual(order.status, "pending")
        self.assertFalse(NativeChainTransfer.objects.filter(invoice=invoice).exists())
        self.assertFalse(LedgerEntry.objects.filter(order=order).exists())

    def test_valid_eth_evidence_atomically_pays_order(self):
        invoice, order=self.invoice()
        with patch("mpw_native_checkout.settlement.verify_eth_transfer",
                   return_value=self.expected_proof(invoice, ETH_TX)) as verifier:
            result=settle_native_invoice(invoice.pk, ETH_TX, ethereum_rpc=lambda *args: {})
        self.assertEqual(result, "paid")
        self.assertEqual(verifier.call_count, 1)
        self.assertEqual(verifier.call_args.args[1].smallest_units, int(invoice.amount_atomic))
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        self.assertEqual(NativeChainTransfer.objects.filter(invoice=invoice).count(), 1)
        self.assertEqual(LedgerEntry.objects.filter(order=order).count(), 1)
        self.assertTrue(can_download_paid_native_order(order.pk, self.user.pk))

    def test_valid_trx_evidence_atomically_pays_order(self):
        invoice, order=self.invoice(asset="TRX")
        with patch("mpw_native_checkout.settlement.verify_trx_transfer",
                   return_value=self.expected_proof(invoice, TRX_TX)):
            result=settle_native_invoice(invoice.pk, TRX_TX, tron_solidity_rpc=lambda *args: {})
        self.assertEqual(result, "paid")
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        self.assertTrue(can_download_paid_native_order(order.pk, self.user.pk))

    def test_idempotent_retry_never_duplicates_ledger(self):
        invoice, order=self.invoice()
        with patch("mpw_native_checkout.settlement.verify_eth_transfer",
                   return_value=self.expected_proof(invoice, ETH_TX)):
            self.assertEqual(settle_native_invoice(invoice.pk, ETH_TX, ethereum_rpc=lambda *args:{}), "paid")
        self.assertEqual(settle_native_invoice(invoice.pk, ETH_TX), "already_paid")
        self.assertEqual(LedgerEntry.objects.filter(order=order).count(),1)

    def test_second_hash_cannot_repay_same_order(self):
        invoice, order=self.invoice()
        with patch("mpw_native_checkout.settlement.verify_eth_transfer",
                   return_value=self.expected_proof(invoice, ETH_TX)):
            settle_native_invoice(invoice.pk, ETH_TX, ethereum_rpc=lambda *args:{})
        with self.assertRaises(SettlementRejected):
            settle_native_invoice(invoice.pk,"0x"+"e"*64)
        self.assertEqual(LedgerEntry.objects.filter(order=order).count(),1)

    def test_missing_trusted_rpc_blocks_payment(self):
        invoice, order=self.invoice()
        with self.assertRaises(SettlementRejected):
            settle_native_invoice(invoice.pk, ETH_TX)
        self.check_unpaid(invoice,order)

    def test_invalid_blockchain_proof_blocks_payment(self):
        invoice, order=self.invoice()
        with patch("mpw_native_checkout.settlement.verify_eth_transfer",
                   side_effect=ValueError("Reverted on Ethereum")):
            with self.assertRaises(ValueError):
                settle_native_invoice(invoice.pk,ETH_TX,ethereum_rpc=lambda *args:{})
        self.check_unpaid(invoice,order)

    def test_unverified_receiving_wallet_blocks_payment(self):
        invoice, order=self.invoice()
        invoice.merchant_ownership_verified_at=None
        invoice.save(update_fields=["merchant_ownership_verified_at"])
        with self.assertRaises(SettlementRejected):
            settle_native_invoice(invoice.pk,ETH_TX,ethereum_rpc=lambda *args:{})
        self.check_unpaid(invoice,order)

    def test_missing_customer_signature_challenge_blocks_payment(self):
        invoice, order=self.invoice()
        invoice.wallet_challenge_id=""
        invoice.save(update_fields=["wallet_challenge_id"])
        with self.assertRaises(SettlementRejected):
            settle_native_invoice(invoice.pk,ETH_TX,ethereum_rpc=lambda *args:{})
        self.check_unpaid(invoice,order)

    def test_payment_disabled_blocks_payment(self):
        invoice, order=self.invoice()
        data=dict(self.book.metadata)
        data["payment_live"]=False
        self.book.metadata=data
        self.book.save(update_fields=["metadata","updated_at"])
        with self.assertRaises(SettlementRejected):
            settle_native_invoice(invoice.pk,ETH_TX,ethereum_rpc=lambda *args:{})
        self.check_unpaid(invoice,order)

    def test_stale_pricing_blocks_payment(self):
        invoice, order=self.invoice()
        invoice.price_observed_at=invoice.issued_at-timedelta(minutes=4)
        invoice.save(update_fields=["price_observed_at"])
        with self.assertRaises(SettlementRejected):
            settle_native_invoice(invoice.pk,ETH_TX,ethereum_rpc=lambda *args:{})
        self.check_unpaid(invoice,order)

    def test_two_orders_cannot_use_same_chain_transaction(self):
        first, first_order=self.invoice()
        second, second_order=self.invoice(amount="2500000000000001")
        with patch("mpw_native_checkout.settlement.verify_eth_transfer",
                   side_effect=lambda tx,q,rpc: self.expected_proof(first,tx)):
            settle_native_invoice(first.pk,ETH_TX,ethereum_rpc=lambda *args:{})
            with self.assertRaises(Exception):
                settle_native_invoice(second.pk,ETH_TX,ethereum_rpc=lambda *args:{})
        self.check_unpaid(second,second_order)
        self.assertEqual(LedgerEntry.objects.count(),1)

    def test_invoice_mutation_during_rpc_blocks_payment(self):
        invoice, order=self.invoice()
        def change_after_chain_validation(tx,q,rpc):
            NativeInvoice.objects.filter(pk=invoice.pk).update(amount_atomic="2000000000000000")
            return self.expected_proof(invoice,tx)
        with patch("mpw_native_checkout.settlement.verify_eth_transfer",
                   side_effect=change_after_chain_validation):
            with self.assertRaises(SettlementRejected):
                settle_native_invoice(invoice.pk,ETH_TX,ethereum_rpc=lambda *args:{})
        self.check_unpaid(invoice,order)

    def test_background_batch_rejects_invalid_and_settles_once(self):
        invoice, order=self.invoice()
        proof=self.expected_proof(invoice,ETH_TX)
        with patch("mpw_native_checkout.settlement.verify_eth_transfer",return_value=proof):
            result=reconcile_discovered_transfers(
                [(invoice.pk,"0xinvalid"),(invoice.pk,ETH_TX),(invoice.pk,ETH_TX)],
                ethereum_rpc=lambda *args:{},
            )
        self.assertEqual(result,[
            (invoice.pk,"not_settled"),(invoice.pk,"paid"),(invoice.pk,"already_paid"),
        ])
        self.assertEqual(LedgerEntry.objects.filter(order=order).count(),1)
