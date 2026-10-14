"""Complete sandbox Django purchase: buyer signature to private file delivery.

No live payment, transfer, gateway, tokens, or real blockchain RPC. The chain
finality result below is a deliberately isolated server-side test double.
"""
import json
import sys
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from eth_account import Account
from eth_account.messages import encode_defunct

from core.models import Product, Order, OrderItem, LedgerEntry
from mpw_commerce.models import CommerceReceipt, CommerceFulfillment
from mpw_commerce.settlement import settle_order_invoice, SettlementRejected
from mpw_commerce.buyer_wallets import invoice_from_verified_buyer
from mpw_commerce.invoicing import TrustedRate


RECEIVING_ETH="0x89149b01f59115B86553561F12438D2ADF517E75"
TX="0x"+"a"*64
TOKEN="c"*32


class FullPrivatePurchaseCycle(TransactionTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        (root/"books").mkdir()
        self.document=root/"books"/"science.pdf"
        self.document.write_bytes(b"%PDF-1.4\nMOJPLAYWIN SANDBOX PAID ONLY\n")
        User=get_user_model()
        self.buyer=User.objects.create_user(username="sandbox-end-to-end-buyer")
        self.stranger=User.objects.create_user(username="sandbox-end-to-end-stranger")
        self.signer=Account.create()
        self.digital=Product.objects.create(
            title="Research publication",product_type="digital",
            price=Decimal("12.00"),currency="USD",active=True,
            metadata={"mpw_commerce":{
                "enabled":True,"fulfillment":"digital",
                "private_file":"books/science.pdf",
            }},
        )
        self.service=Product.objects.create(
            title="Online class",product_type="service",
            price=Decimal("8.00"),currency="USD",active=True,
            metadata={"mpw_commerce":{
                "enabled":True,"fulfillment":"service",
            }},
        )
        self.order=Order.objects.create(
            customer=self.buyer,status="pending",currency="USD",
            total=Decimal("20.00"),
        )
        self.book_item=OrderItem.objects.create(
            order=self.order,product=self.digital,quantity=1,
            unit_price=self.digital.price,currency="USD",
        )
        self.service_item=OrderItem.objects.create(
            order=self.order,product=self.service,quantity=1,
            unit_price=self.service.price,currency="USD",
        )
        self.client=Client(enforce_csrf_checks=True)
        self.client.force_login(self.buyer)
        self.client.cookies["csrftoken"]=TOKEN
        self.opts=override_settings(
            ALLOWED_HOSTS=["mojplaywin.com","www.mojplaywin.com","testserver"],
            MPW_COMMERCE_RELEASE_READY=True,
            MPW_COMMERCE_CUSTOMER_HTTP_ENABLED=True,
            MPW_COMMERCE_BUYER_SIGNATURE_ENABLED=True,
            MPW_COMMERCE_INVOICING_ENABLED=True,
            MPW_COMMERCE_SETTLEMENT_ENABLED=True,
            MPW_COMMERCE_DOWNLOADS_ENABLED=True,
            MPW_COMMERCE_BUYER_CRYPTO_PYTHON=sys.executable,
            MPW_COMMERCE_PRIVATE_ASSET_ROOT=str(root),
        )
        self.opts.enable()
        self.addCleanup(self.opts.disable)

    def post(self,url,params):
        return self.client.post(
            url,data=json.dumps(params),content_type="application/json",
            secure=True,HTTP_HOST="mojplaywin.com",
            HTTP_REFERER="https://mojplaywin.com/",
            HTTP_X_CSRFTOKEN=TOKEN,
        )

    def get(self,url):
        return self.client.get(url,secure=True,HTTP_HOST="mojplaywin.com")

    def invoice(self):
        issued=self.post(reverse("mpw_commerce:challenge"),{
            "order_id":self.order.pk,
            "asset":"ETH",
            "sender":self.signer.address,
        })
        self.assertEqual(issued.status_code,201,issued.content)
        challenge=issued.json()
        signature=Account.sign_message(
            encode_defunct(text=challenge["message"]),self.signer.key,
        ).signature.hex()
        signed=self.post(reverse("mpw_commerce:verify"),{
            "challenge_id":challenge["challenge_id"],
            "signature":signature,
        })
        self.assertEqual(signed.status_code,200,signed.content)
        real_invoice=invoice_from_verified_buyer

        def server_rate(buyer,challenge_id):
            return real_invoice(
                buyer,challenge_id,
                rate_loader=lambda _:TrustedRate(
                    usd_per_asset=Decimal("3000.00"),
                    source="coingecko",
                    observed_at=timezone.now()-timedelta(seconds=5),
                ),
            )
        with patch("mpw_commerce.checkout_views.invoice_from_verified_buyer",
                   side_effect=server_rate):
            quote=self.post(reverse("mpw_commerce:invoice"),{
                "challenge_id":challenge["challenge_id"],
            })
        self.assertEqual(quote.status_code,201,quote.content)
        return quote.json()

    def payment_proof(self,invoice,tx=TX):
        return {
            "finalized":True,
            "order_id":invoice.order_id,
            "network":invoice.network,
            "tx_hash":tx,
            "sender":invoice.expected_sender.lower(),
            "recipient":RECEIVING_ETH.lower(),
            "amount_atomic":int(invoice.amount_atomic),
            "backend":"ethereum-mainnet-verified",
            "block_timestamp":invoice.issued_at+timedelta(seconds=20),
        }

    def test_one_multiline_cart_with_private_download_after_verified_receipt(self):
        doc_url=reverse("mpw_commerce:download",kwargs={"item_id":self.book_item.pk})
        state_url=reverse("mpw_commerce:status",kwargs={"order_id":self.order.pk})
        self.assertEqual(self.get(doc_url).status_code,404)
        quote=self.invoice()
        self.assertEqual(quote["usd_total"],"20.00")
        self.assertEqual(quote["receiver"].lower(),RECEIVING_ETH.lower())
        self.assertEqual(self.get(doc_url).status_code,404)
        self.assertFalse(self.get(state_url).json()["can_access_purchased_items"])

        from mpw_commerce.models import CommerceInvoice
        inv=CommerceInvoice.objects.get(pk=quote["invoice_id"])
        proof=self.payment_proof(inv)
        # Only trusted server verification is permitted to unlock the order.
        verifier=lambda invoice,tx:proof
        self.assertEqual(
            settle_order_invoice(inv.pk,TX,trusted_chain_verifier=verifier),
            "paid",
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,"paid")
        self.assertEqual(LedgerEntry.objects.filter(order=self.order).count(),1)
        self.assertEqual(CommerceReceipt.objects.filter(invoice=inv).count(),1)
        self.assertEqual(CommerceFulfillment.objects.filter(
            item__order=self.order,
        ).count(),2)
        self.assertEqual(self.book_item.mpw_fulfillment.status,"ready")
        self.assertEqual(self.service_item.mpw_fulfillment.status,"queued")
        self.assertTrue(self.get(state_url).json()["can_access_purchased_items"])
        response=self.get(doc_url)
        self.assertEqual(response.status_code,200)
        self.assertIn("attachment",response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content),
                         self.document.read_bytes())
        response.close()
        self.assertEqual(
            settle_order_invoice(inv.pk,TX,trusted_chain_verifier=verifier),
            "already_paid",
        )
        self.assertEqual(LedgerEntry.objects.filter(order=self.order).count(),1)
        self.client.force_login(self.stranger)
        self.assertEqual(self.get(doc_url).status_code,404)
        self.assertEqual(self.get(state_url).status_code,404)

    def test_invalid_chain_receipt_never_unlocks_even_when_wallet_signed(self):
        quote=self.invoice()
        from mpw_commerce.models import CommerceInvoice
        inv=CommerceInvoice.objects.get(pk=quote["invoice_id"])
        proof=self.payment_proof(inv)
        proof["recipient"]="0x"+"e"*40
        with self.assertRaises(SettlementRejected):
            settle_order_invoice(
                inv.pk,TX,trusted_chain_verifier=lambda invoice,tx:proof,
            )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,"pending")
        self.assertFalse(LedgerEntry.objects.filter(order=self.order).exists())
        self.assertEqual(self.get(reverse(
            "mpw_commerce:download",
            kwargs={"item_id":self.book_item.pk},
        )).status_code,404)

    def test_tron_wallet_full_order_payment_and_private_download(self):
        """Offline TRX path: signed text, server quote, receipt and buyer PDF."""
        import hashlib
        from eth_keys import keys
        from eth_utils import keccak
        from mpw_commerce.buyer_signature_worker import BASE58
        from mpw_commerce.models import CommerceInvoice

        private=keys.PrivateKey(bytes([0x21])*32)  # CI fixture, not real funds
        raw_address=b"\x41"+keccak(private.public_key.to_bytes())[-20:]
        checksum=hashlib.sha256(hashlib.sha256(raw_address).digest()).digest()[:4]
        number=int.from_bytes(raw_address+checksum,"big")
        address=""
        while number:
            number,digit=divmod(number,58)
            address=BASE58[digit]+address
        issued=self.post(reverse("mpw_commerce:challenge"),{
            "order_id":self.order.pk,"asset":"TRX","sender":address,
        })
        self.assertEqual(issued.status_code,201,issued.content)
        challenge=issued.json()
        message=challenge["message"].encode("utf-8")
        digest=keccak(b"\x19TRON Signed Message:\n"+
                      str(len(message)).encode("ascii")+message)
        signed=private.sign_msg_hash(digest).to_bytes()
        signature="0x"+(signed[:64]+bytes([signed[-1]+27])).hex()
        verified=self.post(reverse("mpw_commerce:verify"),{
            "challenge_id":challenge["challenge_id"],"signature":signature,
        })
        self.assertEqual(verified.status_code,200,verified.content)

        def trusted_rate(buyer,challenge_id):
            return invoice_from_verified_buyer(
                buyer,challenge_id,
                rate_loader=lambda _:TrustedRate(
                    usd_per_asset=Decimal("0.25"),
                    source="coingecko",
                    observed_at=timezone.now()-timedelta(seconds=5),
                ),
            )
        with patch("mpw_commerce.checkout_views.invoice_from_verified_buyer",
                   side_effect=trusted_rate):
            response=self.post(reverse("mpw_commerce:invoice"),{
                "challenge_id":challenge["challenge_id"],
            })
        self.assertEqual(response.status_code,201,response.content)
        doc=response.json()
        self.assertEqual(doc["network"],"tron-mainnet")
        self.assertEqual(doc["receiver"],
                         "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73")
        self.assertEqual(doc["usd_total"],"20.00")
        invoice=CommerceInvoice.objects.get(pk=doc["invoice_id"])
        trx_hash="a"*64
        server_proof={
            "finalized":True,"order_id":self.order.pk,
            "network":"tron-mainnet","tx_hash":trx_hash,
            "sender":address.lower(),
            "recipient":invoice.recipient.lower(),
            "amount_atomic":int(invoice.amount_atomic),
            "backend":"tron-mainnet-verified",
            "block_timestamp":invoice.issued_at+timedelta(seconds=15),
        }
        self.assertEqual(
            settle_order_invoice(
                invoice.pk,trx_hash,
                trusted_chain_verifier=lambda invoice,tx:server_proof,
            ),
            "paid",
        )
        self.assertEqual(LedgerEntry.objects.filter(order=self.order).count(),1)
        self.assertEqual(self.service_item.mpw_fulfillment.status,"queued")
        downloaded=self.get(reverse(
            "mpw_commerce:download",kwargs={"item_id":self.book_item.pk},
        ))
        self.assertEqual(downloaded.status_code,200)
        self.assertEqual(b"".join(downloaded.streaming_content),
                         self.document.read_bytes())
        downloaded.close()
