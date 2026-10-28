"""Real Django ORM + real ephemeral MariaDB walletless money-to-entitlement test.

Uses minimal dynamic model fixtures with the same observed field names as
cPanel, never imports the real deployed site's data or paths. Never production.
"""
from __future__ import annotations
import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
from pathlib import Path
from datetime import timedelta, timezone
from decimal import Decimal

import pymysql
from services.mpw_trx_walletless_core import PaymentHold, SolidifiedTransfer
from services.mpw_trx_walletless_reservation import reserve_isolated
from services.mpw_walletless_django_test_bridge import (
    settle_to_django_test_database,TrustedNodePair,
)
from services.mpw_walletless_django_test_invoice import reserve_to_django_test_database

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "_walletless_ephemeral_settings")
settings_module=types.ModuleType("_walletless_ephemeral_settings")
settings_module.SECRET_KEY="test-only-key-not-for-production"
settings_module.INSTALLED_APPS=[]
settings_module.USE_TZ=True
settings_module.TIME_ZONE="UTC"
settings_module.ALLOWED_HOSTS=["isolated.test","staging.test","testserver"]
settings_module.DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
settings_module.DATABASES={"default":{
    "ENGINE":"django.db.backends.mysql",
    "NAME":"test_walletless_ci","USER":"walletless","PASSWORD":"local-only-no-money",
    "HOST":"127.0.0.1","PORT":"3306",
    "OPTIONS":{"charset":"utf8mb4"},
}}
settings_module.MPW_WALLETLESS_TRX_TEST_ADAPTER=True
settings_module.MPW_COMMERCE_INVOICING_ENABLED=False
settings_module.MPW_WALLETLESS_TRX_PUBLIC_ENABLED=False
sys.modules["_walletless_ephemeral_settings"]=settings_module

import django
django.setup()
from django.db import models,connection

class User(models.Model):
    name=models.CharField(max_length=40,default='Test Buyer')
    username=models.CharField(max_length=100,unique=True,null=True)
    password=models.CharField(max_length=128,default="!")
    is_active=models.BooleanField(default=True)
    USERNAME_FIELD="username"
    def set_unusable_password(self):
        self.password="!guest-account-cannot-login"
    class Meta:app_label="test_core";db_table="test_mpw_core_user"

class Product(models.Model):
    active=models.BooleanField(default=True)
    currency=models.CharField(max_length=10,default='USD')
    price=models.DecimalField(max_digits=14,decimal_places=2)
    # Synthetic rights evidence: absent by default; explicitly approved only in a test.
    metadata=models.JSONField(default=dict)
    class Meta:app_label="test_core";db_table="test_mpw_core_product"

class Order(models.Model):
    customer_id=models.BigIntegerField()
    total=models.DecimalField(max_digits=14,decimal_places=2)
    currency=models.CharField(max_length=10,default="USD")
    status=models.CharField(max_length=30,default="pending")
    updated_at=models.DateTimeField(auto_now=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:app_label="test_core";db_table="test_mpw_core_order"

class OrderItem(models.Model):
    order=models.ForeignKey(Order,on_delete=models.CASCADE,related_name="items")
    unit_price=models.DecimalField(max_digits=14,decimal_places=2)
    product=models.ForeignKey(Product,on_delete=models.PROTECT,null=True)
    quantity=models.PositiveIntegerField(default=1)
    currency=models.CharField(max_length=10,default="USD")
    kind=models.CharField(max_length=16,default="digital")
    class Meta:app_label="test_core";db_table="test_mpw_core_orderitem"

class LedgerEntry(models.Model):
    order=models.ForeignKey(Order,on_delete=models.CASCADE)
    payment_intent=models.BigIntegerField(null=True)
    entry_type=models.CharField(max_length=30)
    amount=models.DecimalField(max_digits=14,decimal_places=2)
    currency=models.CharField(max_length=10)
    reference=models.CharField(max_length=200,unique=True)
    metadata=models.JSONField(default=dict)
    class Meta:app_label="test_core";db_table="test_mpw_core_ledgerentry"

class CommerceInvoice(models.Model):
    order=models.ForeignKey(Order,on_delete=models.CASCADE)
    network=models.CharField(max_length=32,default='tron-mainnet')
    recipient=models.CharField(max_length=100,default='')
    amount_atomic=models.CharField(max_length=50,default='')
    status=models.CharField(max_length=16)
    class Status:
        AWAITING="awaiting"
    class Meta:app_label="test_commerce";db_table="test_mpw_commerce_invoice"

class CommerceReceipt(models.Model):
    network=models.CharField(max_length=32)
    tx_hash=models.CharField(max_length=80,unique=True)
    class Meta:app_label="test_commerce";db_table="test_mpw_commerce_receipt"

class CommerceFulfillment(models.Model):
    item=models.OneToOneField(OrderItem,on_delete=models.CASCADE)
    kind=models.CharField(max_length=16)
    status=models.CharField(max_length=24)
    class Status:
        READY="ready"
    class Meta:app_label="test_commerce";db_table="test_mpw_commerce_fulfillment"

ARTIFACT=None
def _private_file(item):
    if hasattr(item,"kind"):assert item.kind=="digital"
    return Path(ARTIFACT)

def order_snapshot(order):
    items=list(OrderItem.objects.filter(order=order))
    if len(items)!=1 or order.status!="pending":
        raise ValueError("ineligible")
    item=items[0]
    if item.kind!="digital":
        raise ValueError("not digital")
    return order.total,[(item,item.kind)]

sys.modules["core"]=types.ModuleType("core")
fake_core=types.ModuleType("core.models")
fake_core.Order=Order;fake_core.LedgerEntry=LedgerEntry;fake_core.OrderItem=OrderItem;fake_core.Product=Product
sys.modules["core.models"]=fake_core
sys.modules["mpw_commerce"]=types.ModuleType("mpw_commerce")
fake_models=types.ModuleType("mpw_commerce.models")
fake_models.CommerceInvoice=CommerceInvoice
fake_models.CommerceReceipt=CommerceReceipt
fake_models.CommerceFulfillment=CommerceFulfillment
sys.modules["mpw_commerce.models"]=fake_models
fake_buyer_orders=types.ModuleType("mpw_commerce.buyer_orders")
fake_buyer_orders._eligible=lambda p:bool(p.active and p.currency=="USD" and p.price>0)
sys.modules["mpw_commerce.buyer_orders"]=fake_buyer_orders
fake_settlement=types.ModuleType("mpw_commerce.settlement")
fake_settlement.order_snapshot=order_snapshot
sys.modules["mpw_commerce.settlement"]=fake_settlement
fake_fulfillment=types.ModuleType("mpw_commerce.fulfillment")
fake_fulfillment._private_file=_private_file
sys.modules["mpw_commerce.fulfillment"]=fake_fulfillment

NOW=__import__("datetime").datetime(2026,10,22,3,0,tzinfo=timezone.utc)
RECIPIENT="T"+"A"*33
SENDER="T"+"B"*33
TX_HASH="a"*64
fake_native=types.ModuleType("scripts.mojplaywin_native_chain_verify")
fake_native.tron_address_to_hex=lambda v: "41"+"AB"*20 if v==RECIPIENT else (_ for _ in ()).throw(ValueError("bad recipient"))
sys.modules["scripts.mojplaywin_native_chain_verify"]=fake_native

def raw_conn():
    return pymysql.connect(host="127.0.0.1",user="walletless",password="local-only-no-money",
                           database="test_walletless_ci",autocommit=False)

def proof(source,amount,hash_id=TX_HASH,solidified=True):
    return SolidifiedTransfer(source_id=source,tx_hash=hash_id,network="tron-mainnet",
       recipient=RECIPIENT,sender=SENDER,amount_sun=amount,
       block_time=NOW+timedelta(minutes=1),solidified=solidified,
       transfer_contract=True,execution_success=True)

class RealDjangoWalletlessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global ARTIFACT
        file=tempfile.NamedTemporaryFile(delete=False,suffix=".zip")
        file.write(b"PK\x03\x04minimal-test-only-artifact");file.close()
        ARTIFACT=file.name
        with connection.schema_editor() as editor:
            for obj in (User,Product,Order,OrderItem,LedgerEntry,CommerceInvoice,CommerceReceipt,CommerceFulfillment):
                editor.create_model(obj)
        c=raw_conn()
        for sql in Path("services/sql/mpw_walletless_trx_isolated_v1.sql").read_text().split(";"):
            if sql.strip():
                with c.cursor() as cur:cur.execute(sql)
        c.commit();c.close()

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as editor:
            for obj in (CommerceFulfillment,CommerceReceipt,CommerceInvoice,LedgerEntry,OrderItem,Order,Product,User):
                editor.delete_model(obj)
        Path(ARTIFACT).unlink(missing_ok=True)

    def setUp(self):
        c=raw_conn()
        with c.cursor() as cur:
            for table in ("mpw_walletless_trx_guest_handoff_v1","mpw_walletless_trx_guest_claim_v1","mpw_walletless_trx_guest_rate_v1",
                          "mpw_walletless_trx_entitlement_v1","mpw_walletless_trx_ledger_v1",
                          "mpw_walletless_trx_receipt_v1","mpw_walletless_trx_reservation_v1",
                          "mpw_walletless_trx_allocator_v1"):
                cur.execute("DELETE FROM "+table)
            cur.execute("INSERT INTO mpw_walletless_trx_allocator_v1(recipient) VALUES (%s)",(RECIPIENT,))
        c.commit();c.close()
        for model in (CommerceFulfillment,LedgerEntry,CommerceReceipt,CommerceInvoice,OrderItem,Order,Product,User):
            model.objects.all().delete()
        User.objects.create(pk=42)
        Product.objects.create(pk=779,active=True,currency="USD",price=Decimal("0.03"))
        order=Order.objects.create(customer_id=42,total=Decimal("0.03"),status="pending",currency="USD")
        OrderItem.objects.create(order=order,unit_price=Decimal("0.03"),kind="digital")
        conn=raw_conn()
        try:
            self.invoice_id,self.amount,_=reserve_isolated(conn,order_id=order.pk,
               customer_id=42,recipient=RECIPIENT,usd_total=Decimal("0.03"),
               usd_per_trx=Decimal("0.30"),quote_observed_at=NOW,
               now=NOW,legacy_amount_reserved=lambda amount:False,random_below=lambda n:0)
        finally:conn.close()
        self.order_id=order.pk

    def settle(self,tx=TX_HASH,solid=True):
        p=TrustedNodePair("provider-a","provider-b",
            prove_a=lambda h:proof("provider-a",self.amount,h,solidified=solid),
            prove_b=lambda h:proof("provider-b",self.amount,h),
            audited_as_independent=True)
        return settle_to_django_test_database(self.invoice_id,tx,p)

    def test_paid_receipt_real_ledger_real_fulfillment(self):
        self.assertEqual(self.settle(),"paid")
        order=Order.objects.get(pk=self.order_id)
        self.assertEqual(order.status,"paid")
        self.assertEqual(LedgerEntry.objects.filter(order_id=self.order_id).count(),1)
        record=LedgerEntry.objects.get(order_id=self.order_id)
        self.assertEqual(record.reference,"walletless:tron-mainnet:"+TX_HASH)
        self.assertEqual(record.metadata["payment_method"],"walletless_trx")
        self.assertEqual(CommerceFulfillment.objects.filter(item__order_id=self.order_id,status="ready").count(),1)
        c=raw_conn()
        with c.cursor() as cur:
            cur.execute("SELECT count(*) FROM mpw_walletless_trx_receipt_v1 WHERE invoice_id=%s",(self.invoice_id,))
            self.assertEqual(cur.fetchone()[0],1)
        c.close()

    def test_unverified_proof_does_not_write_django_ledger(self):
        with self.assertRaises(PaymentHold):self.settle(solid=False)
        self.assertEqual(Order.objects.get(pk=self.order_id).status,"pending")
        self.assertFalse(LedgerEntry.objects.filter(order_id=self.order_id).exists())
        self.assertFalse(CommerceFulfillment.objects.filter(item__order_id=self.order_id).exists())

    def test_existing_signed_invoice_blocks_walletless_grant(self):
        CommerceInvoice.objects.create(order_id=self.order_id,status="awaiting")
        with self.assertRaises(PaymentHold):self.settle()
        self.assertFalse(LedgerEntry.objects.filter(order_id=self.order_id).exists())

    def test_no_second_credit_after_finality(self):
        self.settle()
        with self.assertRaises(PaymentHold):self.settle()
        self.assertEqual(LedgerEntry.objects.filter(order_id=self.order_id).count(),1)

    def test_walletless_django_invoice_creation_without_signature(self):
        c=raw_conn()
        with c.cursor() as cur:
            cur.execute("DELETE FROM mpw_walletless_trx_reservation_v1 WHERE id=%s",(self.invoice_id,))
        c.commit();c.close()
        def issue(customer=42):
            return reserve_to_django_test_database(self.order_id,customer,
                rate_provider=lambda:(Decimal("0.30"),NOW),
                configured_receiver=lambda:RECIPIENT,now=NOW)
        i,sun,created=issue()
        self.assertTrue(created)
        self.assertGreaterEqual(sun,100000)
        self.assertLessEqual(sun,116666)
        self.assertEqual(issue(),(i,sun,False))
        with self.assertRaises(PaymentHold):issue(customer=78)
        self.assertFalse(LedgerEntry.objects.filter(order_id=self.order_id).exists())

    def test_signed_invoice_blocks_new_walletless_reservation(self):
        c=raw_conn()
        with c.cursor() as cur:
            cur.execute("DELETE FROM mpw_walletless_trx_reservation_v1 WHERE id=%s",(self.invoice_id,))
        c.commit();c.close()
        CommerceInvoice.objects.create(order_id=self.order_id,status="awaiting")
        with self.assertRaises(PaymentHold):
            reserve_to_django_test_database(self.order_id,42,
                rate_provider=lambda:(Decimal("0.30"),NOW),
                configured_receiver=lambda:RECIPIENT,now=NOW)
        self.assertFalse(LedgerEntry.objects.filter(order_id=self.order_id).exists())

    def test_walletless_web_status_stays_unpaid_without_receipt(self):
        from services.mpw_walletless_django_staging_web import _trusted_status
        state=_trusted_status(connection,self.invoice_id,42)
        self.assertEqual(state['status'],'awaiting')
        self.assertFalse(state['can_download'])
        with self.assertRaises(Exception):
            _trusted_status(connection,self.invoice_id,43)

    def test_walletless_web_auto_status_only_after_real_test_ledger(self):
        from services.mpw_walletless_django_staging_web import _trusted_status
        self.assertEqual(self.settle(),'paid')
        state=_trusted_status(connection,self.invoice_id,42)
        self.assertEqual(state['status'],'paid')
        self.assertTrue(state['can_download'])
        self.assertEqual(state['download_path'],f'/commerce/trx-easy/download/{self.invoice_id}/')
        with self.assertRaises(Exception):
            _trusted_status(connection,self.invoice_id,43)
        LedgerEntry.objects.filter(order_id=self.order_id).delete()
        self.assertFalse(_trusted_status(connection,self.invoice_id,42)['can_download'])

    def test_walletless_web_mobile_invoice_page_has_qr_and_strict_csp(self):
        from django.test import RequestFactory
        from services.mpw_walletless_django_staging_web import _show_invoice
        with connection.cursor() as cur:
            cur.execute(
              """UPDATE mpw_walletless_trx_reservation_v1
                 SET issued_at=UTC_TIMESTAMP(6),
                     expires_at=DATE_ADD(UTC_TIMESTAMP(6), INTERVAL 10 MINUTE)
                 WHERE id=%s""",[self.invoice_id])
        request=RequestFactory().get(f'/commerce/trx-easy/invoice/{self.invoice_id}/',
           secure=True,HTTP_HOST='stage.test')
        request.user=SimpleNamespace(pk=42,is_authenticated=True,is_active=True)
        with patch('services.mpw_walletless_django_staging_web._ensure_test',return_value=connection):
            result=_show_invoice(request,self.invoice_id)
        html=result.content.decode('utf8')
        self.assertEqual(result.status_code,200)
        self.assertIn('Pay TRX in my wallet',html)
        self.assertIn('id="mpw-open-wallet"',html)
        self.assertIn('QR contains the address only',html)
        self.assertEqual(html.count('<script>'),2)
        self.assertIn("frame-ancestors 'none'",result['Content-Security-Policy'])
        self.assertEqual(result['Cache-Control'],'no-store, private, max-age=0')

    def test_walletless_web_paid_download_only_for_owner(self):
        from django.test import RequestFactory
        from django.http import Http404
        from services.mpw_walletless_django_staging_web import _download_paid
        def request(user):
            req=RequestFactory().get(f'/commerce/trx-easy/download/{self.invoice_id}/',
                    secure=True,HTTP_HOST='stage.test')
            req.user=SimpleNamespace(pk=user,is_authenticated=True,is_active=True)
            return req
        with patch('services.mpw_walletless_django_staging_web._ensure_test',return_value=connection):
            with self.assertRaises(Http404): _download_paid(request(42),self.invoice_id)
            self.settle()
            with self.assertRaises(Http404): _download_paid(request(999),self.invoice_id)
            response=_download_paid(request(42),self.invoice_id)
            self.assertEqual(response.status_code,200)
            self.assertIn('attachment',response['Content-Disposition'])
            self.assertEqual(response['Cache-Control'],'no-store, private, max-age=0')
            response.close()

    def test_one_click_buy_creates_real_test_order_invoice_idempotently(self):
        from django.test import RequestFactory
        from django.utils import timezone as tz
        from services.mpw_walletless_django_staging_web import _start_order,_show_invoice
        req=RequestFactory().post("/commerce/trx-easy/start/779/",secure=True,HTTP_HOST="staging.test")
        req.user=SimpleNamespace(pk=42,is_authenticated=True,is_active=True)
        with (patch("services.mpw_walletless_django_staging_web._ensure_test",return_value=connection),
              patch("django.contrib.auth.get_user_model",return_value=User),
              patch("services.mpw_walletless_django_staging_web._rate_provider",
                    side_effect=lambda:(Decimal("0.30"),tz.now())),
              patch("services.mpw_walletless_django_staging_web._configured_receiver",
                    return_value=RECIPIENT)):
            first=_start_order(req,779)
            self.assertEqual(first.status_code,302)
            self.assertIn("/commerce/trx-easy/invoice/",first["Location"])
            qty=Order.objects.count()
            second=_start_order(req,779)
            self.assertEqual(second["Location"],first["Location"])
            self.assertEqual(Order.objects.count(),qty)
            invoice_id=int(first["Location"].strip("/").split("/")[-1])
            page=_show_invoice(req,invoice_id)
            self.assertEqual(page.status_code,200)
            self.assertIn(b'Pay TRX in my wallet',page.content)
            self.assertIn(b'QR contains the address only',page.content)
            self.assertFalse(LedgerEntry.objects.filter(
                order__customer_id=42,metadata__payment_method="walletless_trx").exists())

    def test_anonymous_one_click_checkout_claim_status_paid_download(self):
        from django.test import RequestFactory
        from django.http import Http404
        from services.mpw_walletless_django_guest_claim import COOKIE_NAME,read_guest_buyer
        from services.mpw_walletless_django_guest_staging_web import (
            guest_start_order,guest_show_invoice,guest_invoice_status,guest_download_paid,guest_redeem_wallet_link)
        from django.utils import timezone as tz
        factory=RequestFactory()
        def req(method,path,cookie=None):
            r=getattr(factory,method)(path,secure=True,HTTP_HOST="isolated.test")
            r._dont_enforce_csrf_checks=True
            r.user=SimpleNamespace(is_authenticated=False,is_active=False,pk=None)
            if cookie:r.COOKIES[COOKIE_NAME]=cookie
            return r
        with (patch("django.contrib.auth.get_user_model",return_value=User),
              patch("services.mpw_walletless_django_staging_web._rate_provider",
                    side_effect=lambda:(Decimal("0.30"),tz.now())),
              patch("services.mpw_walletless_django_staging_web._configured_receiver",
                    return_value=RECIPIENT)):
            start=guest_start_order(req("post","/commerce/trx-easy/start/779/"),779)
            self.assertEqual(start.status_code,302)
            self.assertIn(COOKIE_NAME,start.cookies)
            token=start.cookies[COOKIE_NAME].value
            self.assertEqual(start.cookies[COOKIE_NAME]["httponly"],True)
            self.assertEqual(start.cookies[COOKIE_NAME]["secure"],True)
            buyer=read_guest_buyer(token)
            self.assertIsInstance(buyer,int)
            self.assertNotEqual(buyer,42)
            self.assertTrue(User.objects.get(pk=buyer).password.startswith("!"))
            self.assertEqual(User.objects.filter(username__startswith="mpwguest_").count(),1)
            invoice_id=int(start["Location"].strip("/").split("/")[-1])
            page=guest_show_invoice(req("get",start["Location"],token),invoice_id)
            self.assertEqual(page.status_code,200)
            self.assertIn(b'Pay TRX in my wallet',page.content)
            self.assertIn(b'QR contains the address only',page.content)
            self.assertNotIn(token,page.content.decode('utf8'))
            import re
            handoff_match=re.search(r'data-wallet-handoff="(/commerce/trx-easy/claim/[a-f0-9]{64}/)"',
                          page.content.decode("utf8"))
            self.assertIsNotNone(handoff_match)
            new_browser=guest_redeem_wallet_link(
                req("get",handoff_match.group(1)),handoff_match.group(1).strip("/").split("/")[-1])
            self.assertEqual(new_browser.status_code,302)
            second_cookie=new_browser.cookies[COOKIE_NAME].value
            self.assertNotEqual(second_cookie,token)
            self.assertEqual(read_guest_buyer(second_cookie),buyer)
            other_browser=guest_invoice_status(
                 req("get",f"/commerce/trx-easy/status/{invoice_id}/",second_cookie),invoice_id)
            self.assertEqual(other_browser.status_code,200)
            with self.assertRaises(Http404):
                guest_redeem_wallet_link(
                    req("get",handoff_match.group(1)),handoff_match.group(1).strip("/").split("/")[-1])
            repeat=guest_start_order(req("post","/commerce/trx-easy/start/779/",token),779)
            self.assertEqual(repeat["Location"],start["Location"])
            self.assertEqual(User.objects.filter(username__startswith="mpwguest_").count(),1)
            status=guest_invoice_status(req("get","/commerce/trx-easy/status/"+str(invoice_id)+"/",token),invoice_id)
            self.assertEqual(status.json() if hasattr(status,"json") else __import__("json").loads(status.content),{"status":"awaiting","can_download":False})
            with self.assertRaises(Http404):
                guest_download_paid(req("get","/commerce/trx-easy/download/"+str(invoice_id)+"/",token),invoice_id)
            with self.assertRaises(Http404):
                guest_invoice_status(req("get","/commerce/trx-easy/status/"+str(invoice_id)+"/",None),invoice_id)
            with self.assertRaises(Http404):
                guest_invoice_status(req("get","/commerce/trx-easy/status/"+str(invoice_id)+"/",token+"tampered"),invoice_id)
            from services.mpw_walletless_django_staging_web import _trusted_status
            self.assertFalse(_trusted_status(connection,invoice_id,buyer)["can_download"])
            from services.mpw_walletless_django_test_bridge import settle_to_django_test_database,TrustedNodePair
            from datetime import datetime,timezone
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT amount_sun FROM mpw_walletless_trx_reservation_v1 WHERE id=%s",[invoice_id])
                exact_sun=int(cursor.fetchone()[0])
            proof_time=datetime.now(timezone.utc)
            def proof_guest(source):
                return SolidifiedTransfer(
                    source_id=source,tx_hash="d"*64,network="tron-mainnet",
                    recipient=RECIPIENT,sender=SENDER,amount_sun=exact_sun,
                    block_time=proof_time,solidified=True,
                    transfer_contract=True,execution_success=True)
            pair=TrustedNodePair("guest-node-a","guest-node-b",
                  prove_a=lambda tx:proof_guest("guest-node-a"),
                  prove_b=lambda tx:proof_guest("guest-node-b"),
                  audited_as_independent=True)
            self.assertEqual(settle_to_django_test_database(invoice_id,"d"*64,pair),"paid")
            state=guest_invoice_status(
                req("get",f"/commerce/trx-easy/status/{invoice_id}/",token),invoice_id)
            paid=__import__("json").loads(state.content)
            self.assertEqual(paid["status"],"paid")
            self.assertTrue(paid["can_download"])
            self.assertEqual(paid["download_path"],f"/commerce/trx-easy/download/{invoice_id}/")
            download=guest_download_paid(
                req("get",paid["download_path"],token),invoice_id)
            self.assertEqual(download.status_code,200)
            self.assertIn("no-store",download["Cache-Control"])
            self.assertIn("private",download["Cache-Control"])
            self.assertIn("attachment",download["Content-Disposition"])
            download.close()
            with self.assertRaises(Http404):
                guest_download_paid(req("get",paid["download_path"],token+"tampered"),invoice_id)
            with self.assertRaises(Http404):
                guest_download_paid(req("get",paid["download_path"],None),invoice_id)

    def test_guest_wallet_handoff_expiry_and_owner_scoping(self):
        from services.mpw_walletless_django_guest_claim import (
            issue_secondary_guest_cookie_for_handoff,read_guest_buyer)
        from services.mpw_walletless_django_guest_handoff import (
            create_wallet_handoff,redeem_wallet_handoff)
        with connection.cursor() as cur:
            cur.execute("""UPDATE mpw_walletless_trx_reservation_v1
                SET issued_at=UTC_TIMESTAMP(6),
                    expires_at=DATE_ADD(UTC_TIMESTAMP(6),INTERVAL 10 MINUTE)
                WHERE id=%s""",[self.invoice_id])
        with patch("django.contrib.auth.get_user_model",return_value=User):
            cookie=issue_secondary_guest_cookie_for_handoff(42)
            self.assertEqual(read_guest_buyer(cookie),42)
            link=create_wallet_handoff(invoice_id=self.invoice_id,buyer_id=42)
            ticket=link.strip("/").split("/")[-1]
            with self.assertRaises(PaymentHold):
                create_wallet_handoff(invoice_id=self.invoice_id,buyer_id=314)
            with connection.cursor() as cur:
                cur.execute(
                    """UPDATE mpw_walletless_trx_guest_handoff_v1
                       SET expires_at=DATE_SUB(UTC_TIMESTAMP(6),INTERVAL 1 SECOND)
                       WHERE ticket_sha256=%s""",
                    [__import__("hashlib").sha256(ticket.encode()).hexdigest()])
            with self.assertRaises(PaymentHold):
                redeem_wallet_handoff(ticket)
            with self.assertRaises(PaymentHold):
                redeem_wallet_handoff("0"*64)
            self.assertEqual(read_guest_buyer(cookie),42)

    def test_guest_rate_limit_five_per_hour(self):
        from services.mpw_walletless_django_guest_claim import create_guest_buyer
        with patch("django.contrib.auth.get_user_model",return_value=User):
            for index in range(5):
                buyer,token=create_guest_buyer(remote_ip="203.0.113.101")
                self.assertIsInstance(buyer,int)
                self.assertTrue(token)
            with self.assertRaises(PaymentHold):
                create_guest_buyer(remote_ip="203.0.113.101")
            with self.assertRaises(PaymentHold):
                create_guest_buyer(remote_ip="untrusted")
            with connection.cursor() as c:
                c.execute("SELECT COUNT(*) FROM mpw_walletless_trx_guest_claim_v1")
                self.assertEqual(c.fetchone()[0],5)

    def test_missing_private_file_cannot_grant(self):
        global ARTIFACT
        before=ARTIFACT
        ARTIFACT="/path/that/does/not/exist/product.zip"
        try:
            with self.assertRaises(PaymentHold):self.settle()
            self.assertFalse(CommerceFulfillment.objects.exists())
        finally: ARTIFACT=before

if __name__=="__main__":unittest.main()
