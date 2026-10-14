"""Isolated generic storefront ETH/TRX order tests. No real payment operations.

The fake verifier below is test-only; production requires trusted blockchain
RPC and indexer integration before the two release gates can ever be enabled.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Product, Order, OrderItem, LedgerEntry
from mpw_commerce.policy import order_snapshot, CommercePolicyError
from mpw_commerce.invoicing import (
    reserve_order_invoice, VerifiedBuyer, TrustedRate, InvoiceRejected
)
from mpw_commerce.models import (
    CommerceInvoice, CommerceReceipt, CommerceFulfillment
)
from mpw_commerce.settlement import settle_order_invoice, SettlementRejected
from mpw_commerce.entitlements import can_access_purchased_digital_item

ETH_RECIPIENT="0x89149b01f59115B86553561F12438D2ADF517E75"
ETH_SENDER="0x"+"c"*40
HASH_1="0x"+"a"*64
HASH_2="0x"+"b"*64
LIVE={
    "MPW_COMMERCE_INVOICING_ENABLED":True,
    "MPW_COMMERCE_SETTLEMENT_ENABLED":True,
}


class SitewideCommerceTests(TestCase):
    def setUp(self):
        self.now=timezone.now()
        U=get_user_model()
        self.buyer=U.objects.create_user(username="new-store-buyer",password="test-only")
        self.other=U.objects.create_user(username="new-store-other",password="test-only")
        self.digital=self.product("Digital research paper","digital",Decimal("5.00"))
        self.member=self.product("Gold membership","subscription",Decimal("20.00"))
        self.physical=self.product("Chess equipment","physical",Decimal("30.00"))
        self.service=self.product("Professional lesson","service",Decimal("15.00"))

    def product(self,title,kind,price):
        return Product.objects.create(
            title=title,product_type=kind,price=price,currency="USD",
            active=True,metadata={
                "mpw_commerce":{"enabled":True,"fulfillment":kind}
            }
        )

    def order(self,choices=None):
        choices=choices or [(self.digital,2),(self.member,1),(self.physical,1)]
        amount=sum((p.price*q for p,q in choices),Decimal("0.00"))
        order=Order.objects.create(customer=self.buyer,total=amount,
                                   currency="USD",status="pending")
        lines=[]
        for p,q in choices:
            lines.append(OrderItem.objects.create(
                order=order,product=p,unit_price=p.price,
                quantity=q,currency="USD"
            ))
        return order,lines

    def buyer_proof(self):
        return VerifiedBuyer(sender=ETH_SENDER,challenge_id="signed-test-buyer-01",
                             verified_at=self.now)

    def quote(self):
        return TrustedRate(usd_per_asset=Decimal("3000.00"),
                           source="coingecko",
                           observed_at=self.now-timedelta(seconds=5))

    def invoice(self,order):
        return reserve_order_invoice(
            order.pk,"ETH",buyer=self.buyer_proof(),quote=self.quote(),now=self.now
        )

    def good_receipt(self,invoice,tx=HASH_1):
        return {
            "finalized":True, "order_id":invoice.order_id,
            "network":"ethereum-mainnet","tx_hash":tx,
            "sender":invoice.expected_sender.lower(),
            "recipient":ETH_RECIPIENT.lower(),
            "amount_atomic":int(invoice.amount_atomic),
            "backend":"ethereum-mainnet-verified",
            "block_timestamp":invoice.issued_at+timedelta(seconds=30),
        }

    def test_all_sales_and_settlement_default_off(self):
        order,_=self.order()
        with override_settings(MPW_COMMERCE_INVOICING_ENABLED=False):
            with self.assertRaises(InvoiceRejected):
                self.invoice(order)
        with override_settings(**LIVE):
            invoice=self.invoice(order)
        with override_settings(MPW_COMMERCE_SETTLEMENT_ENABLED=False):
            verifier=Mock()
            with self.assertRaises(SettlementRejected):
                settle_order_invoice(invoice.pk,HASH_1,trusted_chain_verifier=verifier)
            verifier.assert_not_called()

    @override_settings(**LIVE)
    def test_multiple_items_one_payment_and_separate_fulfillment(self):
        order,items=self.order()
        self.assertTrue(self.invoice(order).total_usd==Decimal("60.00"))
        invoice=order.mpw_commerce_invoice
        proof=self.good_receipt(invoice)
        verifier=Mock(return_value=proof)
        self.assertEqual(
            settle_order_invoice(invoice.pk,HASH_1,trusted_chain_verifier=verifier),
            "paid"
        )
        order.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(order.status,"paid")
        self.assertEqual(invoice.status,"paid")
        self.assertEqual(LedgerEntry.objects.filter(order=order).count(),1)
        self.assertEqual(CommerceReceipt.objects.filter(invoice=invoice).count(),1)
        self.assertEqual(CommerceFulfillment.objects.filter(item__order=order).count(),3)
        self.assertEqual(items[0].mpw_fulfillment.status,"ready")
        self.assertEqual(items[1].mpw_fulfillment.status,"queued")
        self.assertEqual(items[2].mpw_fulfillment.status,"awaiting_dispatch")
        self.assertTrue(can_access_purchased_digital_item(items[0].pk,self.buyer.pk))
        self.assertFalse(can_access_purchased_digital_item(items[0].pk,self.other.pk))
        self.assertFalse(can_access_purchased_digital_item(items[1].pk,self.buyer.pk))
        self.assertEqual(verifier.call_count,1)

    @override_settings(**LIVE)
    def test_no_owner_approval_in_payment_or_download(self):
        order,items=self.order([(self.digital,1),(self.service,1)])
        invoice=self.invoice(order)
        proof=self.good_receipt(invoice)
        self.assertEqual(
            settle_order_invoice(invoice.pk,HASH_1,trusted_chain_verifier=lambda *_:proof),
            "paid",
        )
        self.assertTrue(can_access_purchased_digital_item(items[0].pk,self.buyer.pk))
        self.assertEqual(items[1].mpw_fulfillment.status,"queued")

    @override_settings(**LIVE)
    def test_idempotent_replay_does_not_double_charge_or_deliver(self):
        order,items=self.order()
        invoice=self.invoice(order)
        proof=self.good_receipt(invoice)
        self.assertEqual(settle_order_invoice(
            invoice.pk,HASH_1,trusted_chain_verifier=lambda *_:proof),"paid")
        verifier=Mock(side_effect=AssertionError("Already-paid must not requery chain"))
        self.assertEqual(settle_order_invoice(
            invoice.pk,HASH_1,trusted_chain_verifier=verifier),"already_paid")
        verifier.assert_not_called()
        self.assertEqual(LedgerEntry.objects.filter(order=order).count(),1)
        self.assertEqual(CommerceFulfillment.objects.filter(item__order=order).count(),3)

    @override_settings(**LIVE)
    def test_invalid_receipt_never_marks_order_paid(self):
        order,_=self.order([(self.digital,1)])
        invoice=self.invoice(order)
        for key,value in (
            ("finalized",False),("recipient","0x"+"b"*40),
            ("sender","0x"+"f"*40),("amount_atomic",1),
            ("network","wrong-chain"),("order_id",9898),
            ("block_timestamp",self.now-timedelta(hours=1)),
        ):
            with self.subTest(field=key):
                proof=self.good_receipt(invoice)
                proof[key]=value
                with self.assertRaises(SettlementRejected):
                    settle_order_invoice(invoice.pk,HASH_1,
                                         trusted_chain_verifier=lambda *_:proof)
                invoice.refresh_from_db()
                self.assertEqual(invoice.status,"awaiting")
                self.assertFalse(LedgerEntry.objects.filter(order=invoice.order).exists())

    @override_settings(**LIVE)
    def test_price_or_order_line_tampering_blocks_sale(self):
        order,items=self.order()
        order.total=Decimal("0.01")
        order.save(update_fields=["total"])
        with self.assertRaises(InvoiceRejected):
            self.invoice(order)
        order.total=Decimal("60.00")
        order.save(update_fields=["total"])
        items[0].unit_price=Decimal("0.01")
        items[0].save(update_fields=["unit_price"])
        with self.assertRaises(InvoiceRejected):
            self.invoice(order)

    @override_settings(**LIVE)
    def test_inactive_or_not_configured_product_blocks_sale(self):
        order,_=self.order([(self.digital,1)])
        self.digital.active=False
        self.digital.save(update_fields=["active"])
        with self.assertRaises(InvoiceRejected):
            self.invoice(order)
        self.digital.active=True
        self.digital.metadata={"mpw_commerce":{"enabled":False,"fulfillment":"digital"}}
        self.digital.save(update_fields=["active","metadata"])
        with self.assertRaises(InvoiceRejected):
            self.invoice(order)

    @override_settings(**LIVE)
    def test_other_currency_not_silently_converted_to_usd(self):
        order,_=self.order([(self.digital,1)])
        order.currency="IRR"
        order.save(update_fields=["currency"])
        with self.assertRaises(InvoiceRejected):
            self.invoice(order)

    @override_settings(**LIVE)
    def test_stale_buyer_proof_and_rate_block_invoice(self):
        order,_=self.order()
        older=VerifiedBuyer(sender=ETH_SENDER,challenge_id="signed-test-buyer-01",
                            verified_at=self.now-timedelta(minutes=10))
        with self.assertRaises(InvoiceRejected):
            reserve_order_invoice(order.pk,"ETH",buyer=older,
                                  quote=self.quote(),now=self.now)
        stale=TrustedRate(usd_per_asset=Decimal("3000"),source="coingecko",
                          observed_at=self.now-timedelta(minutes=10))
        with self.assertRaises(InvoiceRejected):
            reserve_order_invoice(order.pk,"ETH",buyer=self.buyer_proof(),
                                  quote=stale,now=self.now)

    @override_settings(**LIVE)
    def test_second_invoice_same_order_is_rejected(self):
        order,_=self.order()
        self.invoice(order)
        with self.assertRaises(InvoiceRejected):
            self.invoice(order)

    @override_settings(**LIVE)
    def test_finalized_transfer_cannot_be_reused_to_pay_another_order(self):
        order,_=self.order([(self.digital,1)])
        invoice=self.invoice(order)
        proof=self.good_receipt(invoice)
        self.assertEqual(settle_order_invoice(
            invoice.pk,HASH_1,trusted_chain_verifier=lambda *_:proof),"paid")
        next_order,_=self.order([(self.member,1)])
        another=self.invoice(next_order)
        forged=self.good_receipt(another)
        with self.assertRaises(Exception):
            settle_order_invoice(another.pk,HASH_1,
                                 trusted_chain_verifier=lambda *_:forged)
        next_order.refresh_from_db()
        self.assertEqual(next_order.status,"pending")
        self.assertEqual(LedgerEntry.objects.filter(order=next_order).count(),0)

    @override_settings(**LIVE)
    def test_paid_fulfillment_fails_closed_if_ledger_absent(self):
        order,items=self.order([(self.digital,1)])
        invoice=self.invoice(order)
        proof=self.good_receipt(invoice)
        settle_order_invoice(invoice.pk,HASH_1,trusted_chain_verifier=lambda *_:proof)
        LedgerEntry.objects.filter(order=order).delete()
        self.assertFalse(can_access_purchased_digital_item(items[0].pk,self.buyer.pk))
