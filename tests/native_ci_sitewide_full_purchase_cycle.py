"""Full offline checkout: buyer signs, rate quotes, ETH finalized RPC,
auto-watcher settles atomically, ledger grants the buyer's PRIVATE file.

Uses ephemeral test keys, temporary sample file, synthetic chain/indexer
responses, temporary SQLite DB. No mainnet traffic or live assets.
"""
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from eth_account import Account
from eth_account.messages import encode_defunct

from core.models import LedgerEntry,Order,OrderItem,Product
from mpw_commerce.auto_reconcile import reconcile_pending_orders
from mpw_commerce.buyer_wallets import invoice_from_verified_buyer
from mpw_commerce.invoicing import TrustedRate
from mpw_commerce.models import CommerceFulfillment,CommerceInvoice,CommerceReceipt
from mpw_commerce.trusted_chain import verify_with_trusted_rpc
from scripts.mojplaywin_direct_wallet_discovery import Candidate

ETH_TO="0x89149b01f59115B86553561F12438D2ADF517E75"
HASH="0x"+"9"*64
BLOCK_HASH="0x"+"6"*64
CSRF="B"*32
FLAGS={
    "MPW_COMMERCE_RELEASE_READY":True,
    "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED":True,
    "MPW_COMMERCE_BUYER_SIGNATURE_ENABLED":True,
    "MPW_COMMERCE_INVOICING_ENABLED":True,
    "MPW_COMMERCE_BUYER_CRYPTO_PYTHON":sys.executable,
    "MPW_COMMERCE_AUTORECONCILE_ENABLED":True,
    "MPW_COMMERCE_SETTLEMENT_ENABLED":True,
    "MPW_COMMERCE_REAL_RPC_ENABLED":True,
    "MPW_COMMERCE_DOWNLOADS_ENABLED":True,
}


class WholeSiteAutomaticBuyerCycleTests(TransactionTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.private_asset=self.root/"premium-research.pdf"
        self.private_asset.write_bytes(b"%PDF-1.4\nEphemeral premium content\n")
        self.settings=override_settings(
            **FLAGS,MPW_COMMERCE_PRIVATE_ASSET_ROOT=str(self.root),
        )
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        User=get_user_model()
        self.buyer=User.objects.create_user(username="e2e-purchase-buyer")
        self.other=User.objects.create_user(username="e2e-other-buyer")
        self.wallet=Account.create()
        self.digital=Product.objects.create(
            title="Professional course book",product_type="digital",active=True,
            price=Decimal("10.00"),currency="USD",
            metadata={"mpw_commerce":{
                "enabled":True,"fulfillment":"digital",
                "private_file":"premium-research.pdf",
            }},
        )
        self.membership=Product.objects.create(
            title="Membership month",product_type="subscription",active=True,
            price=Decimal("5.00"),currency="USD",
            metadata={"mpw_commerce":{"enabled":True,"fulfillment":"subscription"}},
        )
        self.order=Order.objects.create(
            customer=self.buyer,status="pending",total=Decimal("15.00"),
            currency="USD",
        )
        self.book_line=OrderItem.objects.create(
            order=self.order,product=self.digital,quantity=1,
            unit_price=Decimal("10.00"),currency="USD",
        )
        self.member_line=OrderItem.objects.create(
            order=self.order,product=self.membership,quantity=1,
            unit_price=Decimal("5.00"),currency="USD",
        )
        self.client=Client(enforce_csrf_checks=True)
        self.client.force_login(self.buyer)
        self.client.cookies["csrftoken"]=CSRF
        self.challenge_url=reverse("mpw_commerce:challenge")
        self.verify_url=reverse("mpw_commerce:verify")
        self.invoice_url=reverse("mpw_commerce:invoice")
        self.status_url=reverse(
            "mpw_commerce:status",kwargs={"order_id":self.order.pk},
        )
        self.download_url=reverse(
            "mpw_commerce:download",kwargs={"item_id":self.book_line.pk},
        )

    def post(self,url,body):
        return self.client.post(
            url,data=json.dumps(body),content_type="application/json",
            secure=True,HTTP_HOST="mojplaywin.com",
            HTTP_REFERER="https://mojplaywin.com/commerce/",
            HTTP_X_CSRFTOKEN=CSRF,
        )

    def fake_chain_rpc(self,invoice):
        mined_at=invoice.issued_at+timedelta(seconds=15)
        b=100
        eth_tx={
            "hash":HASH,"to":ETH_TO,"from":self.wallet.address,
            "value":hex(int(invoice.amount_atomic)),
            "blockNumber":hex(b),"blockHash":BLOCK_HASH,
        }
        receipt={
            "transactionHash":HASH,"status":"0x1",
            "blockNumber":hex(b),"blockHash":BLOCK_HASH,
        }
        block={"hash":BLOCK_HASH,"timestamp":hex(int(mined_at.timestamp()))}
        def eth(method,params):
            return {
                "eth_chainId":"0x1",
                "eth_getTransactionByHash":eth_tx,
                "eth_getTransactionReceipt":receipt,
                "eth_blockNumber":hex(b+20),
                "eth_getBlockByNumber":block,
            }[method]
        return eth

    def test_signed_checkout_auto_settles_and_grants_only_its_buyer(self):
        reply=self.post(self.challenge_url,{
            "order_id":self.order.pk,"asset":"ETH",
            "sender":self.wallet.address,
        })
        self.assertEqual(reply.status_code,201,reply.content)
        challenge=reply.json()
        sig=Account.sign_message(
            encode_defunct(text=challenge["message"]),self.wallet.key,
        ).signature.hex()
        response=self.post(self.verify_url,{
            "challenge_id":challenge["challenge_id"],"signature":sig,
        })
        self.assertEqual(response.status_code,200,response.content)

        def rate_provider(user,challenge_id):
            from django.utils import timezone
            return invoice_from_verified_buyer(
                user,challenge_id,
                rate_loader=lambda _:TrustedRate(
                    usd_per_asset=Decimal("3000"),source="coingecko",
                    observed_at=timezone.now()-timedelta(seconds=5),
                ),
            )
        with patch(
            "mpw_commerce.checkout_views.invoice_from_verified_buyer",
            side_effect=rate_provider,
        ):
            result=self.post(self.invoice_url,{
                "challenge_id":challenge["challenge_id"],
            })
        self.assertEqual(result.status_code,201,result.content)
        payment=result.json()
        self.assertEqual(payment["usd_total"],"15.00")
        self.assertEqual(payment["receiver"],ETH_TO)
        invoice=CommerceInvoice.objects.get(pk=payment["invoice_id"])
        self.assertEqual(self.order.status,"pending")
        self.assertEqual(CommerceFulfillment.objects.count(),0)

        candidate=Candidate(
            "ethereum-mainnet",HASH,self.wallet.address.lower(),
            ETH_TO.lower(),invoice.amount_atomic,
            int((invoice.issued_at+timedelta(seconds=15)).timestamp()*1000),
        )
        def trusted(inv,tx):
            return verify_with_trusted_rpc(
                inv,tx,eth_rpc=self.fake_chain_rpc(inv),
            )
        with patch(
            "mpw_commerce.auto_reconcile.discover_trx",
            side_effect=AssertionError("No TRON query on ETH-only purchase"),
        ):
            summary=reconcile_pending_orders(
                now=invoice.issued_at+timedelta(seconds=35),
                eth_scanner=lambda **kwargs:[candidate],
                trx_scanner=lambda **kwargs: (_ for _ in ()).throw(
                    AssertionError("No unrelated TRON scan")
                ),
                verifier=trusted,
            )
        self.assertEqual(summary["matched"],1)
        self.assertEqual(summary["paid"],1)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,"paid")
        self.assertEqual(LedgerEntry.objects.filter(order=self.order).count(),1)
        self.assertEqual(CommerceReceipt.objects.filter(invoice=invoice).count(),1)
        self.assertEqual(self.book_line.mpw_fulfillment.status,"ready")
        self.assertEqual(self.member_line.mpw_fulfillment.status,"queued")
        status=self.client.get(
            self.status_url,secure=True,HTTP_HOST="mojplaywin.com",
        )
        self.assertEqual(status.status_code,200)
        self.assertTrue(status.json()["can_access_purchased_items"])
        paid_file=self.client.get(
            self.download_url,secure=True,HTTP_HOST="mojplaywin.com",
        )
        self.assertEqual(paid_file.status_code,200)
        self.assertEqual(
            b"".join(paid_file.streaming_content),
            self.private_asset.read_bytes(),
        )
        paid_file.close()

        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(
                self.download_url,secure=True,HTTP_HOST="mojplaywin.com",
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                self.status_url,secure=True,HTTP_HOST="mojplaywin.com",
            ).status_code,
            404,
        )
