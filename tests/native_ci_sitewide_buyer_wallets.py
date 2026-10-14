"""Offline authenticated buyer wallet linkage and unique invoice checks.

Only ephemeral CI test keys sign text. No wallet transfer or real purchase.
"""
from datetime import timedelta
from decimal import Decimal
import sys
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from django.utils import timezone

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys import keys
from eth_utils import keccak

from core.models import Product,Order,OrderItem
from mpw_commerce.buyer_wallets import (
    issue_buyer_wallet_challenge,submit_buyer_wallet_signature,
    invoice_from_verified_buyer,WalletLinkRejected,challenge_message,
    fetch_server_rate,
)
from mpw_commerce.buyer_signature_worker import verify_message,BASE58
from mpw_commerce.invoicing import TrustedRate
from mpw_commerce.models import BuyerWalletChallenge,CommerceInvoice

FLAGS={
    "MPW_COMMERCE_BUYER_SIGNATURE_ENABLED":True,
    "MPW_COMMERCE_INVOICING_ENABLED":True,
}


class BuyerWalletCheckoutTests(TestCase):
    def setUp(self):
        self.now=timezone.now()
        User=get_user_model()
        self.customer=User.objects.create_user(username="buyer-wallet-ci")
        self.stranger=User.objects.create_user(username="stranger-wallet-ci")
        self.eth=Account.create()
        self.other_key=Account.create()
        self.product=Product.objects.create(
            title="Multilingual chess book",product_type="digital",
            currency="USD",price=Decimal("13.00"),active=True,
            metadata={"mpw_commerce":{"enabled":True,"fulfillment":"digital"}},
        )
        self.order=Order.objects.create(
            customer=self.customer,status="pending",
            total=Decimal("13.00"),currency="USD",
        )
        OrderItem.objects.create(
            order=self.order,product=self.product,quantity=1,
            unit_price=Decimal("13.00"),currency="USD",
        )
        self.flags=override_settings(**FLAGS)
        self.flags.enable()
        self.addCleanup(self.flags.disable)

    def challenge(self):
        return issue_buyer_wallet_challenge(
            self.order.pk,self.customer,"ETH",self.eth.address,now=self.now,
        )

    def signature(self,text,key=None):
        return Account.sign_message(
            encode_defunct(text=text),
            key or self.eth.key,
        ).signature.hex()

    def quote(self):
        return TrustedRate(
            usd_per_asset=Decimal("3000.00"),
            source="coingecko",
            observed_at=self.now,
        )

    def test_disabled_gate_never_issues_checkout_challenge(self):
        with override_settings(MPW_COMMERCE_BUYER_SIGNATURE_ENABLED=False):
            with self.assertRaises(WalletLinkRejected):
                self.challenge()
        self.assertFalse(BuyerWalletChallenge.objects.exists())

    def test_order_belongs_to_authenticated_customer_only(self):
        with self.assertRaises(WalletLinkRejected):
            issue_buyer_wallet_challenge(
                self.order.pk,self.stranger,"ETH",self.eth.address,now=self.now,
            )
        self.assertFalse(BuyerWalletChallenge.objects.exists())

    def test_real_ephemeral_eth_signature_creates_one_order_invoice(self):
        challenge,text=self.challenge()
        with override_settings(MPW_COMMERCE_BUYER_CRYPTO_PYTHON=sys.executable):
            self.assertTrue(submit_buyer_wallet_signature(
                self.customer,challenge.pk,self.signature(text),
                now=self.now+timedelta(seconds=1),
            ))
        with self.assertRaises(WalletLinkRejected):
            submit_buyer_wallet_signature(
                self.customer,challenge.pk,self.signature(text),
                now=self.now+timedelta(seconds=2),
            )
        invoice=invoice_from_verified_buyer(
            self.customer,challenge.pk,now=self.now+timedelta(seconds=2),
            rate_loader=lambda asset:self.quote(),
        )
        self.assertEqual(invoice.order_id,self.order.pk)
        self.assertEqual(invoice.asset,"ETH")
        self.assertEqual(invoice.expected_sender,self.eth.address)
        self.assertEqual(invoice.total_usd,Decimal("13.00"))
        challenge.refresh_from_db()
        self.assertIsNotNone(challenge.used_at)
        with self.assertRaises(WalletLinkRejected):
            invoice_from_verified_buyer(
                self.customer,challenge.pk,now=self.now+timedelta(seconds=3),
                rate_loader=lambda asset:self.quote(),
            )
        self.assertEqual(CommerceInvoice.objects.count(),1)

    def test_other_test_wallet_signature_cannot_authorize_payment(self):
        challenge,text=self.challenge()
        with override_settings(MPW_COMMERCE_BUYER_CRYPTO_PYTHON=sys.executable):
            self.assertFalse(submit_buyer_wallet_signature(
                self.customer,challenge.pk,self.signature(text,self.other_key.key),
                now=self.now+timedelta(seconds=1),
            ))
        challenge.refresh_from_db()
        self.assertEqual(challenge.failed_attempts,1)
        self.assertIsNone(challenge.verified_at)
        with self.assertRaises(WalletLinkRejected):
            invoice_from_verified_buyer(
                self.customer,challenge.pk,now=self.now+timedelta(seconds=2),
                rate_loader=lambda asset:self.quote(),
            )

    def test_signature_bound_to_specific_order_message(self):
        first,message=self.challenge()
        second,other_message=self.challenge()
        self.assertNotEqual(message,other_message)
        with override_settings(MPW_COMMERCE_BUYER_CRYPTO_PYTHON=sys.executable):
            self.assertFalse(submit_buyer_wallet_signature(
                self.customer,second.pk,self.signature(message),
                now=self.now+timedelta(seconds=1),
            ))
        self.assertIsNone(BuyerWalletChallenge.objects.get(pk=second.pk).verified_at)

    def test_unsigned_or_expired_invoice_is_rejected(self):
        challenge,_=self.challenge()
        with self.assertRaises(WalletLinkRejected):
            invoice_from_verified_buyer(
                self.customer,challenge.pk,now=self.now+timedelta(seconds=2),
                rate_loader=lambda asset:self.quote(),
            )
        with self.assertRaises(WalletLinkRejected):
            submit_buyer_wallet_signature(
                self.customer,challenge.pk,"00",
                now=self.now+timedelta(minutes=6),
            )

    def test_challenge_rate_limit_blocks_nonstop_sign_requests(self):
        for _ in range(6):
            self.challenge()
        with self.assertRaises(WalletLinkRejected):
            self.challenge()
        self.assertEqual(BuyerWalletChallenge.objects.count(),6)

    def test_server_rate_mapping_does_not_accept_customer_supplied_usd_price(self):
        from scripts.mojplaywin_direct_wallet_invoice import SpotRate
        observed=int(self.now.timestamp())
        sample={
            "ETH":SpotRate(asset="ETH",usd_per_asset="2000",
                           provider="coingecko",observed_at_epoch=observed),
            "TRX":SpotRate(asset="TRX",usd_per_asset="0.2",
                           provider="coingecko",observed_at_epoch=observed),
        }
        with patch("scripts.mojplaywin_direct_wallet_rates.fetch_fresh_rates",
                   return_value=sample):
            rate=fetch_server_rate("ETH")
        self.assertEqual(rate.usd_per_asset,Decimal("2000"))
        self.assertEqual(rate.source,"coingecko")


class TronTextSignatureTests(TestCase):
    def test_only_signed_tron_text_with_matching_sender_is_valid(self):
        private=keys.PrivateKey(b"\x21"*32)
        raw_address=b"\x41"+keccak(private.public_key.to_bytes())[-20:]
        import hashlib
        full=raw_address+hashlib.sha256(
            hashlib.sha256(raw_address).digest()
        ).digest()[:4]
        n=int.from_bytes(full,"big")
        address=""
        while n:
            n,mod=divmod(n,58)
            address=BASE58[mod]+address
        message=("MojPlayWin Customer Wallet Link\n"+
                 "No token spending approval is requested\n"+
                 "Order 123 Customer 2 Random nonce of sufficient length")
        bytes_to_sign=message.encode("utf-8")
        digest=keccak(b"\x19TRON Signed Message:\n"+
                      str(len(bytes_to_sign)).encode()+bytes_to_sign)
        raw_signature=private.sign_msg_hash(digest).to_bytes()
        signature="0x"+(raw_signature[:64]+bytes([raw_signature[-1]+27])).hex()
        request={
            "asset":"TRX","address":address,
            "message":message,"signature":signature,
        }
        self.assertTrue(verify_message(request))
        self.assertFalse(verify_message({**request,"message":message+"altered"}))
