"""Real Django ORM + real ephemeral MariaDB walletless money-to-entitlement test.

Uses minimal dynamic model fixtures with the same observed field names as
cPanel, never imports the real deployed site's data or paths. Never production.
"""
from __future__ import annotations
import os
import sys
import types
import unittest
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

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "_walletless_ephemeral_settings")
settings_module=types.ModuleType("_walletless_ephemeral_settings")
settings_module.SECRET_KEY="test-only-key-not-for-production"
settings_module.INSTALLED_APPS=[]
settings_module.USE_TZ=True
settings_module.TIME_ZONE="UTC"
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

class Order(models.Model):
    customer_id=models.BigIntegerField()
    total=models.DecimalField(max_digits=14,decimal_places=2)
    currency=models.CharField(max_length=10,default="USD")
    status=models.CharField(max_length=30,default="pending")
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:app_label="test_core";db_table="test_mpw_core_order"

class OrderItem(models.Model):
    order=models.ForeignKey(Order,on_delete=models.CASCADE,related_name="items")
    unit_price=models.DecimalField(max_digits=14,decimal_places=2)
    kind=models.CharField(max_length=16,default="digital")
    class Meta:app_label="test_core";db_table="test_mpw_core_orderitem"

class LedgerEntry(models.Model):
    order=models.ForeignKey(Order,on_delete=models.CASCADE)
    payment_intent_id=models.BigIntegerField(null=True)
    entry_type=models.CharField(max_length=30)
    amount=models.DecimalField(max_digits=14,decimal_places=2)
    currency=models.CharField(max_length=10)
    reference=models.CharField(max_length=200,unique=True)
    metadata=models.JSONField(default=dict)
    class Meta:app_label="test_core";db_table="test_mpw_core_ledgerentry"

class CommerceInvoice(models.Model):
    order=models.ForeignKey(Order,on_delete=models.CASCADE)
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
    assert item.kind=="digital"
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
fake_core.Order=Order;fake_core.LedgerEntry=LedgerEntry
sys.modules["core.models"]=fake_core
sys.modules["mpw_commerce"]=types.ModuleType("mpw_commerce")
fake_models=types.ModuleType("mpw_commerce.models")
fake_models.CommerceInvoice=CommerceInvoice
fake_models.CommerceReceipt=CommerceReceipt
fake_models.CommerceFulfillment=CommerceFulfillment
sys.modules["mpw_commerce.models"]=fake_models
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
            for obj in (Order,OrderItem,LedgerEntry,CommerceInvoice,CommerceReceipt,CommerceFulfillment):
                editor.create_model(obj)
        c=raw_conn()
        for sql in Path("services/sql/mpw_walletless_trx_isolated_v1.sql").read_text().split(";"):
            if sql.strip():
                with c.cursor() as cur:cur.execute(sql)
        c.commit();c.close()

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as editor:
            for obj in (CommerceFulfillment,CommerceReceipt,CommerceInvoice,LedgerEntry,OrderItem,Order):
                editor.delete_model(obj)
        Path(ARTIFACT).unlink(missing_ok=True)

    def setUp(self):
        c=raw_conn()
        with c.cursor() as cur:
            for table in ("mpw_walletless_trx_entitlement_v1","mpw_walletless_trx_ledger_v1",
                          "mpw_walletless_trx_receipt_v1","mpw_walletless_trx_reservation_v1",
                          "mpw_walletless_trx_allocator_v1"):
                cur.execute("DELETE FROM "+table)
            cur.execute("INSERT INTO mpw_walletless_trx_allocator_v1(recipient) VALUES (%s)",(RECIPIENT,))
        c.commit();c.close()
        for model in (CommerceFulfillment,LedgerEntry,CommerceReceipt,CommerceInvoice,OrderItem,Order):
            model.objects.all().delete()
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

    def test_missing_private_file_cannot_grant(self):
        global ARTIFACT
        before=ARTIFACT
        ARTIFACT="/path/that/does/not/exist/product.zip"
        try:
            with self.assertRaises(PaymentHold):self.settle()
            self.assertFalse(CommerceFulfillment.objects.exists())
        finally: ARTIFACT=before

if __name__=="__main__":unittest.main()
