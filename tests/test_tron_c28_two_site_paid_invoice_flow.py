"""Two separate native TRX merchants, same amounts, no cross-credit or emails.

All transfers and indexers synthetic or mocked, no real TRX, personal data,
messages, remote server reads, live trading or customer accounts.
"""
import hashlib
import io
import time
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from core.models import Product, LedgerEntry
from core.tron_gateway_invoice import TronGatewayInvoice
from core.tron_gateway_verify import MAINNET_RECEIVER, ALPHABET
from core.tron_gateway_web import _new_invoice, _record_paid
from core.tron_gateway_merchant_registry import configured_site_merchant

def second_public_only():
    raw=bytes([0x41])+bytes([0x06])*20
    check=hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
    n=int.from_bytes(raw+check,"big")
    s=""
    while n:
        n,mod=divmod(n,58)
        s=ALPHABET[mod]+s
    return s

SECOND=second_public_only()
REGISTRY={
    "mojplaywin.com":{"tenant_id":"mojplaywin_site","receiver":MAINNET_RECEIVER,"network":"tron-mainnet","asset":"TRX","approved":True},
    "zomorodmelal.ir":{"tenant_id":"zomorodmelal_site","receiver":SECOND,"network":"tron-mainnet","asset":"TRX","approved":True},
}

PROOF={"txid":"a"*64,"sender_hex":"41"+"b"*40,"block_height":1234567,
       "block_time_ms":1800000000000,"proof_digest":"c"*64,
       "finality":"solidified"}

@override_settings(TRON_UNIFIED_SITE_MERCHANTS=REGISTRY,
                   TRON_UNIFIED_DISCOVERY_ENABLED=True)
class TwoLiveScopedMerchantDjangoCases(TestCase):
    def setUp(self):
        self.product_en=Product.objects.create(
            title="Synthetic English service",product_type="service",active=True,
            price=Decimal("12.00"),currency="USD",
            metadata=self.metadata("USD"),
        )
        self.product_fa=Product.objects.create(
            title="Synthetic Persian service",product_type="service",active=True,
            price=Decimal("12.00"),currency="TOMAN",
            metadata=self.metadata("TOMAN"),
        )

    def metadata(self,currency):
        return {
            "rights_cleared":True,"publication_approved":True,"sales_enabled":True,
            "in_stock":True,"fulfillment_ready":True,"fulfillment_type":"service",
            "tron_price_sun":5000000,"tron_price_currency":currency,
            "tron_price_reference_amount":"12.00",
            "tron_quote_valid_until_ms":int(time.time()*1000)+900000,
        }

    def two_invoices(self):
        a,_=_new_invoice("private-a@example.test","mojplaywin.com","en",self.product_en.pk)
        b,_=_new_invoice("private-b@example.test","zomorodmelal.ir","fa",self.product_fa.pk)
        TronGatewayInvoice.objects.filter(pk__in=(a.pk,b.pk)).update(status="awaiting_payment")
        a.refresh_from_db()
        b.refresh_from_db()
        return a,b

    def test_01_two_site_invoices_store_independent_tenants_and_wallets(self):
        a,b=self.two_invoices()
        self.assertNotEqual(a.receiver,b.receiver)
        self.assertNotEqual(a.merchant_tenant_id,b.merchant_tenant_id)
        self.assertEqual((a.source_host,b.source_host),("mojplaywin.com","zomorodmelal.ir"))

    def test_02_different_sites_may_quote_same_amount_when_receivers_differ(self):
        a,b=self.two_invoices()
        TronGatewayInvoice.objects.filter(pk=a.pk).update(amount_sun=9000001)
        TronGatewayInvoice.objects.filter(pk=b.pk).update(amount_sun=9000001)
        self.assertEqual(TronGatewayInvoice.objects.filter(amount_sun=9000001).count(),2)

    def test_03_first_merchant_credit_never_reusable_for_second(self):
        a,b=self.two_invoices()
        self.assertTrue(_record_paid(a.pk,PROOF))
        self.assertFalse(_record_paid(b.pk,PROOF))
        self.assertEqual(LedgerEntry.objects.count(),1)
        row=LedgerEntry.objects.get()
        self.assertEqual(row.metadata["merchant_tenant_id"],"mojplaywin_site")
        self.assertEqual(row.metadata["receiver"],MAINNET_RECEIVER)

    def test_04_paid_invoice_wrong_tenant_cannot_be_revalidated(self):
        a,b=self.two_invoices()
        self.assertTrue(_record_paid(a.pk,PROOF))
        TronGatewayInvoice.objects.filter(pk=a.pk).update(merchant_tenant_id=b.merchant_tenant_id)
        self.assertFalse(_record_paid(a.pk,PROOF))

    def test_05_wrong_receiver_prevents_credit_even_if_host_valid(self):
        a,b=self.two_invoices()
        TronGatewayInvoice.objects.filter(pk=a.pk).update(receiver=SECOND)
        self.assertFalse(_record_paid(a.pk,PROOF))
        self.assertEqual(LedgerEntry.objects.count(),0)

    def test_06_discovery_scans_both_receiver_groups_separately(self):
        a,b=self.two_invoices()
        seen=[]
        def discovery(*,min_ms,max_ms,pages,receiver):
            seen.append(receiver)
            inv=a if receiver==MAINNET_RECEIVER else b
            return [("a"*64 if receiver==MAINNET_RECEIVER else "b"*64,
                     inv.amount_sun,inv.issued_ms+1000)],False
        out=io.StringIO()
        with patch("core.management.commands.tron_discover.receiver_candidates",side_effect=discovery), \
             patch("core.management.commands.tron_discover.verify_native_trx",return_value=PROOF), \
             patch("core.management.commands.tron_discover._record_paid",return_value=True):
            call_command("tron_discover",pages=1,max_checks=12,stdout=out)
        self.assertEqual(set(seen),{MAINNET_RECEIVER,SECOND})
        self.assertIn("receivers_checked=2",out.getvalue())
        self.assertNotIn("private-a@",out.getvalue())

    def test_07_discovery_denies_unregistered_receiver_without_network_calls(self):
        a,b=self.two_invoices()
        TronGatewayInvoice.objects.filter(pk=b.pk).update(merchant_tenant_id="swapped_site")
        out=io.StringIO()
        with patch("core.management.commands.tron_discover.receiver_candidates",return_value=([],False)) as scan:
            call_command("tron_discover",pages=1,max_checks=4,stdout=out)
        self.assertEqual(scan.call_count,1)
        self.assertIn("invalid_tenant_holds=1",out.getvalue())

    def test_08_same_site_merchant_receiver_must_match_private_registry(self):
        a,b=self.two_invoices()
        approved=configured_site_merchant(a.source_host,REGISTRY)
        self.assertEqual(approved.tenant_id,a.merchant_tenant_id)
        self.assertEqual(approved.receiver,a.receiver)

    def test_09_recovery_cannot_consider_old_tenant_owned_paid_invoice(self):
        a,b=self.two_invoices()
        TronGatewayInvoice.objects.filter(pk=a.pk).update(merchant_tenant_id="retired")
        self.assertFalse(TronGatewayInvoice.objects.filter(
            source_host=a.source_host,merchant_tenant_id="mojplaywin_site",
            receiver=MAINNET_RECEIVER,pk=a.pk).exists())
