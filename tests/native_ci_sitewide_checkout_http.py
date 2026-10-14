"""Private Django buyer checkout protocol tests (no real cryptocurrency).

CI-only routes. Real ETH signatures use ephemeral test keys; all exchange
rates come from a mocked SERVER function, not request JSON or the browser.
"""
from datetime import datetime,timezone
from decimal import Decimal
import json
import sys
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client,TestCase,override_settings
from django.urls import reverse

from eth_account import Account
from eth_account.messages import encode_defunct

from core.models import Product,Order,OrderItem
from mpw_commerce.invoicing import TrustedRate
from mpw_commerce.buyer_wallets import invoice_from_verified_buyer
from mpw_commerce.models import CommerceInvoice

CSRF="A"*32
RELEASE={
    "MPW_COMMERCE_RELEASE_READY":True,
    "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED":True,
    "MPW_COMMERCE_BUYER_SIGNATURE_ENABLED":True,
    "MPW_COMMERCE_INVOICING_ENABLED":True,
    "MPW_COMMERCE_BUYER_CRYPTO_PYTHON":sys.executable,
}


class PrivateCheckoutHTTPTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.buyer=User.objects.create_user(username="http-wallet-buyer")
        self.other=User.objects.create_user(username="http-wallet-stranger")
        self.key=Account.create()
        self.product=Product.objects.create(
            title="Secure ebook",product_type="digital",price=Decimal("12.00"),
            currency="USD",active=True,
            metadata={"mpw_commerce":{"enabled":True,"fulfillment":"digital"}},
        )
        self.order=Order.objects.create(
            customer=self.buyer,total=Decimal("12.00"),currency="USD",
            status="pending",
        )
        OrderItem.objects.create(
            order=self.order,product=self.product,quantity=1,
            unit_price=self.product.price,currency="USD",
        )
        self.client=Client(enforce_csrf_checks=True)
        self.client.force_login(self.buyer)
        self.client.cookies["csrftoken"]=CSRF
        self.guard=override_settings(**RELEASE)
        self.guard.enable()
        self.addCleanup(self.guard.disable)
        self.challenge_url=reverse("mpw_commerce:challenge")
        self.verify_url=reverse("mpw_commerce:verify")
        self.invoice_url=reverse("mpw_commerce:invoice")
        self.status_url=reverse(
            "mpw_commerce:status",kwargs={"order_id":self.order.pk},
        )

    def post(self,url,payload,*,host="mojplaywin.com",csrf=True):
        kwargs={"secure":True,"HTTP_HOST":host}
        if csrf:
            kwargs["HTTP_X_CSRFTOKEN"]=CSRF
        return self.client.post(
            url,data=json.dumps(payload),content_type="application/json",**kwargs,
        )

    def issue(self):
        result=self.post(self.challenge_url,{
            "order_id":self.order.pk,"asset":"ETH","sender":self.key.address,
        })
        self.assertEqual(result.status_code,201,result.content)
        return result.json()

    def test_unauthenticated_checkout_is_login_protected(self):
        self.client.logout()
        response=self.post(self.challenge_url,{
            "order_id":self.order.pk,"asset":"ETH","sender":self.key.address,
        })
        self.assertEqual(response.status_code,302)

    def test_absent_csrf_and_other_domains_cannot_issue_checkout(self):
        payload={"order_id":self.order.pk,"asset":"ETH","sender":self.key.address}
        self.assertEqual(self.post(self.challenge_url,payload,csrf=False).status_code,403)
        self.assertEqual(self.post(
            self.challenge_url,payload,host="zomorodmelal.ir",
        ).status_code,404)
        self.assertFalse(CommerceInvoice.objects.exists())

    def test_release_switch_off_returns_no_checkout(self):
        with override_settings(MPW_COMMERCE_RELEASE_READY=False):
            self.assertEqual(self.post(self.challenge_url,{
                "order_id":self.order.pk,"asset":"ETH","sender":self.key.address,
            }).status_code,404)

    def test_price_and_payment_state_cannot_be_client_supplied(self):
        self.assertEqual(self.post(self.challenge_url,{
            "order_id":self.order.pk,"asset":"ETH","sender":self.key.address,
            "usd_total":"0.01",
        }).status_code,400)
        self.assertEqual(self.post(self.invoice_url,{
            "challenge_id":1,"paid":True,
        }).status_code,400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,"pending")
        self.assertFalse(CommerceInvoice.objects.exists())

    def test_unverified_wallet_cannot_generate_public_payment_quote(self):
        challenge=self.issue()
        result=self.post(self.invoice_url,{
            "challenge_id":challenge["challenge_id"],
        })
        self.assertEqual(result.status_code,400)
        self.assertFalse(CommerceInvoice.objects.exists())

    def test_full_ephemeral_signed_checkout_and_private_status(self):
        challenge=self.issue()
        signature=Account.sign_message(
            encode_defunct(text=challenge["message"]),self.key.key,
        ).signature.hex()
        verify=self.post(self.verify_url,{
            "challenge_id":challenge["challenge_id"],
            "signature":signature,
        })
        self.assertEqual(verify.status_code,200,verify.content)
        self.assertTrue(verify.json()["verified"])

        def server_quote_only(buyer,challenge_id):
            now=datetime.now(timezone.utc)
            return invoice_from_verified_buyer(
                buyer,challenge_id,
                rate_loader=lambda asset:TrustedRate(
                    usd_per_asset=Decimal("3000"),
                    source="coingecko",observed_at=now,
                ),
            )
        with patch("mpw_commerce.checkout_views.invoice_from_verified_buyer",
                   side_effect=server_quote_only):
            invoice=self.post(self.invoice_url,{
                "challenge_id":challenge["challenge_id"],
            })
        self.assertEqual(invoice.status_code,201,invoice.content)
        doc=invoice.json()
        self.assertEqual(doc["usd_total"],"12.00")
        self.assertEqual(doc["asset"],"ETH")
        self.assertEqual(doc["network"],"ethereum-mainnet")
        self.assertEqual(int(doc["amount_atomic"]),int(
            Decimal(doc["amount_native"])*Decimal(10)**18
        ))
        self.assertEqual(self.order.status,"pending")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,"pending")
        self.assertEqual(self.client.get(
            self.status_url,secure=True,HTTP_HOST="mojplaywin.com",
        ).json()["state"],"awaiting")
        with patch("mpw_commerce.checkout_views.invoice_from_verified_buyer") as reserve:
            self.assertEqual(self.post(self.invoice_url,{
                "challenge_id":challenge["challenge_id"],
            }).status_code,400)
            reserve.assert_called_once()
        self.assertEqual(CommerceInvoice.objects.count(),1)

    def test_other_user_cannot_read_buyer_order_status(self):
        data=self.issue()
        self.client.force_login(self.other)
        result=self.client.get(
            self.status_url,secure=True,HTTP_HOST="mojplaywin.com",
        )
        self.assertEqual(result.status_code,404)
