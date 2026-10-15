"""Gated cart issuance on disposable DB: no real transfers or payments."""
from decimal import Decimal
import json
import tempfile
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase,Client,override_settings
from django.urls import reverse

from core.models import KnowledgeArticle, Product, Order, OrderItem
from mpw_commerce.models import CommerceOrderRequest,CommerceInvoice

FLAGS={
    "MPW_COMMERCE_RELEASE_READY":True,
    "MPW_COMMERCE_INVOICING_ENABLED":True,
    "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED":True,
    "MPW_COMMERCE_SETTLEMENT_ENABLED":True,
    "MPW_COMMERCE_REAL_RPC_ENABLED":True,
    "MPW_COMMERCE_DOWNLOADS_ENABLED":True,
}
CSRF="A"*32


class BuyerCartTests(TestCase):
    def setUp(self):
        U=get_user_model()
        self.buyer=U.objects.create_user(username="cart-buyer")
        self.stranger=U.objects.create_user(username="cart-stranger")
        self.owner=U.objects.create_user(username="cart-product-owner")
        article=KnowledgeArticle.objects.create(
            title="Research-linked original book",slug="paid-cart-book",
            content="Authoritative content reviewed for publishing",published=True,
        )
        self.tmp=tempfile.TemporaryDirectory(prefix="mpw-private-ci-")
        self.addCleanup(self.tmp.cleanup)
        Path(self.tmp.name,"verified.pdf").write_bytes(b"%PDF-1.4\nprivate bytes fixture")
        self.product=Product.objects.create(
            title="Complete independently approved research book",
            owner=self.owner,knowledge_article=article,
            product_type="digital_book",price=Decimal("12.00"),
            currency="USD",active=True,
            metadata={
                "factory_publication_permission":True,
                "asset_verified":True,"quality_approved":True,
                "license_verified":True,
                "mpw_commerce":{
                    "enabled":True,"fulfillment":"digital",
                    "private_file":"verified.pdf",
                },
            },
        )
        self.client=Client(enforce_csrf_checks=True)
        self.client.force_login(self.buyer)
        self.client.cookies["csrftoken"]=CSRF
        self.url=reverse("mpw_commerce:order")
        self.flags=override_settings(
            **FLAGS,MPW_COMMERCE_PRIVATE_ASSET_ROOT=self.tmp.name
        )
        self.flags.enable()
        self.addCleanup(self.flags.disable)
        self.proof=patch(
            "mpw_native_checkout.wallet_ownership.proven_assets",
            return_value={"ETH":True,"TRX":False}
        )
        self.proof.start()
        self.addCleanup(self.proof.stop)

    def payload(self,**kwargs):
        d={"product_id":self.product.pk,"quantity":1,
           "asset":"ETH","request_id":str(uuid4())}
        d.update(kwargs)
        return d

    def post(self,d,host="mojplaywin.com",csrf=True):
        return self.client.post(
            self.url,data=json.dumps(d),content_type="application/json",
            secure=True,HTTP_HOST=host,
            HTTP_REFERER="https://"+host+"/store/",
            **({"HTTP_X_CSRFTOKEN":CSRF} if csrf else {}),
        )

    def assert_empty(self):
        self.assertEqual(Order.objects.count(),0)
        self.assertFalse(OrderItem.objects.exists())
        self.assertFalse(CommerceOrderRequest.objects.exists())
        self.assertFalse(CommerceInvoice.objects.exists())

    def test_first_order_pending_replay_is_same_one_order(self):
        d=self.payload()
        first=self.post(d)
        self.assertEqual(first.status_code,201,first.content)
        self.assertEqual(first.json()["status"],"pending")
        self.assertEqual(first.json()["amount_usd"],"12.00")
        second=self.post(d)
        self.assertEqual(second.status_code,200,second.content)
        self.assertEqual(first.json()["order_id"],second.json()["order_id"])
        self.assertEqual(Order.objects.count(),1)
        self.assertEqual(OrderItem.objects.count(),1)
        self.assertEqual(CommerceOrderRequest.objects.count(),1)
        self.assertFalse(CommerceInvoice.objects.exists())

    def test_reused_token_other_product_or_person_rejected(self):
        d=self.payload()
        self.assertEqual(self.post(d).status_code,201)
        self.assertEqual(self.post(dict(d,product_id=999)).status_code,409)
        self.client.force_login(self.stranger)
        self.assertEqual(self.post(d).status_code,409)
        self.assertEqual(Order.objects.count(),1)

    def test_no_wallet_ownership_no_checkout_even_with_flags_on(self):
        with patch("mpw_native_checkout.wallet_ownership.proven_assets",
                   return_value={"ETH":False,"TRX":False}):
            self.assertEqual(self.post(self.payload()).status_code,404)
        self.assert_empty()

    def test_trx_cannot_sell_without_its_own_wallet_proof(self):
        self.assertEqual(self.post(self.payload(asset="TRX")).status_code,404)
        self.assert_empty()

    def test_feature_flag_disabled_cannot_write_to_order_tables(self):
        for flag in FLAGS:
            with self.subTest(flag=flag),override_settings(**{flag:False}):
                self.assertEqual(self.post(self.payload()).status_code,404)
                self.assert_empty()

    def test_missing_rights_approval_and_missing_asset_all_fail_closed(self):
        for flag in ("license_verified","quality_approved",
                     "asset_verified","factory_publication_permission"):
            data=dict(self.product.metadata)
            data[flag]=False
            self.product.metadata=data
            self.product.save(update_fields=["metadata"])
            self.assertEqual(self.post(self.payload()).status_code,404)
            self.assert_empty()
            data[flag]=True
            self.product.metadata=data
            self.product.save(update_fields=["metadata"])
        Path(self.tmp.name,"verified.pdf").unlink()
        self.assertEqual(self.post(self.payload()).status_code,409)
        self.assert_empty()

    def test_csrf_domain_price_injection_and_bad_key_rejected(self):
        self.assertEqual(self.post(self.payload(),csrf=False).status_code,403)
        self.assertEqual(self.post(self.payload(),host="zomorodmelal.ir").status_code,404)
        self.assertEqual(self.post(dict(self.payload(),amount_usd="0.01")).status_code,400)
        self.assertEqual(self.post(self.payload(request_id="not-uuid")).status_code,400)
        self.assertEqual(self.post(self.payload(quantity=2)).status_code,400)
        self.assert_empty()

    def test_anonymous_user_cannot_create_order(self):
        self.client.logout()
        self.assertEqual(self.post(self.payload()).status_code,403)
        self.assert_empty()

    def test_limit_pending_orders_and_reject_orphan_retry(self):
        for _ in range(5):
            Order.objects.create(customer=self.buyer,total=Decimal("3.00"),
                                 currency="USD",status="pending")
        current=Order.objects.count()
        self.assertEqual(self.post(self.payload()).status_code,429)
        self.assertEqual(Order.objects.count(),current)
        self.assertFalse(CommerceOrderRequest.objects.exists())
