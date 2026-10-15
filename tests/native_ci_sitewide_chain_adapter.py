"""Offline tests for dynamic USD order quotes using the trusted native verifier."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Product, Order, OrderItem
from mpw_commerce.invoicing import VerifiedBuyer, TrustedRate, reserve_order_invoice
from mpw_commerce.trusted_chain import verify_with_trusted_rpc, ChainAdapterUnavailable
from scripts.mojplaywin_native_chain_verify import (
    LockedQuote, _validate_quote, VerificationError,
)

ON={"MPW_COMMERCE_INVOICING_ENABLED":True,"MPW_COMMERCE_REAL_RPC_ENABLED":True}
ETH_SENDER="0x"+"c"*40
ETH_TX="0x"+"a"*64


class SitewideChainVerifierTests(TestCase):
    def setUp(self):
        self.now=timezone.now()
        from django.contrib.auth import get_user_model
        self.user=get_user_model().objects.create_user(username="new-rpc-buyer")
        p=Product.objects.create(
            title="Research bundle",product_type="digital",price=Decimal("35.00"),
            currency="USD",active=True,
            metadata={"mpw_commerce":{"enabled":True,"fulfillment":"digital"}},
        )
        self.order=Order.objects.create(
            customer=self.user,total=Decimal("70.00"),currency="USD",
            status="pending",
        )
        OrderItem.objects.create(
            order=self.order,product=p,quantity=2,
            unit_price=p.price,currency="USD",
        )

    def invoice(self):
        return reserve_order_invoice(
            self.order.pk,"ETH",
            buyer=VerifiedBuyer(
                sender=ETH_SENDER,challenge_id="buyer-signed-challenge",
                verified_at=self.now,
            ),
            quote=TrustedRate(usd_per_asset=Decimal("3000.00"),source="coingecko",
                              observed_at=self.now),
            now=self.now,
        )

    def test_non_book_usd_quotes_are_supported_and_validated(self):
        q=LockedQuote(order_id=11,network="ethereum-mainnet",
                      smallest_units=10000,expected_sender=ETH_SENDER,
                      created_at_ms=1000,expires_at_ms=1001,
                      quote_currency="USD",quote_amount="70.00")
        _validate_quote(q,"ethereum-mainnet")
        for bad in ("0.00","7.5","0.000","-2.00","nan","Infinity","99999999999999999.00"):
            with self.subTest(price=bad):
                from dataclasses import replace
                with self.assertRaises(VerificationError):
                    _validate_quote(replace(q,quote_amount=bad),"ethereum-mainnet")

    def test_rpc_disabled_makes_zero_network_requests(self):
        with override_settings(MPW_COMMERCE_INVOICING_ENABLED=True):
            invoice=self.invoice()
        eth_rpc=Mock(side_effect=AssertionError("Must not call real RPC"))
        with override_settings(MPW_COMMERCE_REAL_RPC_ENABLED=False):
            with self.assertRaises(ChainAdapterUnavailable):
                verify_with_trusted_rpc(invoice,ETH_TX,eth_rpc=eth_rpc)
        eth_rpc.assert_not_called()

    @override_settings(**ON)
    def test_dynamic_order_quote_reaches_verified_eth_adapter(self):
        invoice=self.invoice()
        stamp=int((self.now+timedelta(seconds=30)).timestamp()*1000)
        fake={
            "network":"ethereum-mainnet","order_id":invoice.order_id,
            "transaction_hash":ETH_TX,
            "amount_smallest_units":int(invoice.amount_atomic),
            "sender":ETH_SENDER,"recipient":invoice.recipient.lower(),
            "confirmed_blocks":12,"mined_timestamp_ms":stamp,
        }
        with patch("mpw_commerce.trusted_chain.verify_eth_transfer",
                   return_value=fake) as check:
            result=verify_with_trusted_rpc(invoice,ETH_TX)
        passed=check.call_args.args[1]
        self.assertEqual(passed.quote_amount,"70.00")
        self.assertEqual(passed.smallest_units,int(invoice.amount_atomic))
        self.assertEqual(result["backend"],"ethereum-mainnet-verified")
        self.assertTrue(result["finalized"])
        self.assertEqual(result["block_timestamp"].timestamp()*1000,stamp)

    @override_settings(**ON)
    def test_chain_adapter_rejects_missing_timestamp(self):
        invoice=self.invoice()
        fake={
            "network":"ethereum-mainnet","order_id":invoice.order_id,
            "transaction_hash":ETH_TX,
            "amount_smallest_units":int(invoice.amount_atomic),
            "sender":ETH_SENDER,"recipient":invoice.recipient.lower(),
        }
        with patch("mpw_commerce.trusted_chain.verify_eth_transfer",
                   return_value=fake):
            with self.assertRaises(ChainAdapterUnavailable):
                verify_with_trusted_rpc(invoice,ETH_TX)
