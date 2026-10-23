"""Real isolated MariaDB end-to-end for the EXACT commercial adapter.

The database is a fresh, throwaway CI instance. No production wallet, order,
financial record, credential or HTTP access. Synthetic 2-node proof only.
"""
from __future__ import annotations
import contextlib
import json
import sys
import unittest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from types import SimpleNamespace

from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.http import Http404

from tests.test_mpw_walletless_existing_intent_pilot import (
    ExistingNoDDLWalletlessTests as Base, PaymentIntent,
    PaymentWebhookEvent,ExistingLedgerEntry,
)
from tests import test_mpw_walletless_real_django_orm_e2e as fixture
from services.mpw_walletless_django_test_bridge import TrustedNodePair
from services.mpw_trx_walletless_core import PaymentHold

# Fixture aliases reproduce the *actual* cPanel module path (verified on site).
sys.modules["mpw_commerce.downloads"]=sys.modules["mpw_commerce.fulfillment"]
from services.mpw_walletless_commercial_intent import (
    reserve_commercial_intent,settle_commercial_intent,commercial_buyer_status,
    reconcile_commercial_intent_from_candidates,open_commercial_paid_file,
)
from services.mpw_trx_commercial_web import (
    _show_invoice,_invoice_status,_download_paid,_start_order,
)

class CommercialMariaDBTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.setUpClass()
    @classmethod
    def tearDownClass(cls):
        Base.tearDownClass()
    def setUp(self):
        Base.setUp(self)
        self.stack=contextlib.ExitStack()
        self.stack.enter_context(patch.object(settings,"ALLOWED_HOSTS",["mojplaywin.com","testserver","staging.test","isolated.test"],create=True))
        for name,value in (
            ("DEBUG",False),("MPW_COMMERCE_RELEASE_READY",True),
            ("MPW_COMMERCE_DOWNLOADS_ENABLED",True),
            ("MPW_WALLETLESS_TRX_PUBLIC_ENABLED",True),
            ("MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED",True),
        ):
            self.stack.enter_context(patch.object(settings,name,value,create=True))
    def tearDown(self):
        self.stack.close()
    def reserve(self,customer=42,order_id=None,random_below=lambda _:0):
        return reserve_commercial_intent(order_id or self.order_id,customer,
            rate_provider=lambda:(Decimal("0.30"),fixture.NOW),
            configured_receiver=lambda:fixture.RECIPIENT,
            now=fixture.NOW,random_below=random_below)
    def pair(self,confirmed=True):
        pk=PaymentIntent.objects.filter(order_id=self.order_id).first()
        assert pk is not None
        from services.mpw_walletless_commercial_intent import _decode
        invoice=_decode(pk)
        return TrustedNodePair("provider-a","provider-b",
            prove_a=lambda tx:fixture.proof("provider-a",invoice.amount_sun,tx,solidified=confirmed),
            prove_b=lambda tx:fixture.proof("provider-b",invoice.amount_sun,tx),
            audited_as_independent=True)
    def test_commercial_invoice_and_paid_private_file(self):
        pk,invoice,created=self.reserve()
        self.assertTrue(created)
        self.assertEqual(self.reserve(),(pk,invoice,False))
        self.assertEqual(commercial_buyer_status(pk,42),{"status":"awaiting","can_download":False})
        with self.assertRaises(PaymentHold):
            open_commercial_paid_file(pk,42)
        self.assertEqual(settle_commercial_intent(pk,fixture.TX_HASH,self.pair()),"paid")
        self.assertEqual(fixture.Order.objects.get(pk=self.order_id).status,"paid")
        self.assertEqual(PaymentIntent.objects.get(pk=pk).status,"paid")
        self.assertEqual(PaymentWebhookEvent.objects.filter(payment_intent_id=pk).count(),1)
        self.assertEqual(ExistingLedgerEntry.objects.filter(order_id=self.order_id).count(),1)
        self.assertEqual(fixture.CommerceFulfillment.objects.filter(item__order_id=self.order_id,status="ready").count(),1)
        self.assertEqual(commercial_buyer_status(pk,42),{"status":"paid","can_download":True,
                         "download_path":f"/commerce/trx-easy/download/{pk}/"})
        with open_commercial_paid_file(pk,42) as f:
            self.assertEqual(f.read(),b"PK\x03\x04minimal-test-only-artifact")
        with self.assertRaises(PaymentHold):
            open_commercial_paid_file(pk,43)
        with self.assertRaises(PaymentHold):
            settle_commercial_intent(pk,fixture.TX_HASH,self.pair())
        self.assertEqual(ExistingLedgerEntry.objects.count(),1)
    def test_missing_receipt_disables_existing_access(self):
        pk,_,_=self.reserve()
        self.assertEqual(settle_commercial_intent(pk,fixture.TX_HASH,self.pair()),"paid")
        PaymentWebhookEvent.objects.filter(payment_intent_id=pk).delete()
        self.assertFalse(commercial_buyer_status(pk,42)["can_download"])
    def test_wrong_owner_and_failed_finality_never_pay(self):
        pk,_,_=self.reserve()
        with self.assertRaises(PaymentHold):
            settle_commercial_intent(pk,fixture.TX_HASH,self.pair(confirmed=False))
        self.assertFalse(ExistingLedgerEntry.objects.exists())
        self.assertFalse(PaymentWebhookEvent.objects.exists())
        self.assertFalse(fixture.CommerceFulfillment.objects.exists())
        with self.assertRaises(PaymentHold):
            commercial_buyer_status(pk,43)
        self.assertFalse(commercial_buyer_status(pk,42)["can_download"])
    def test_candidate_based_server_settlement_one_time_only(self):
        pk,invoice,_=self.reserve()
        seen=[]
        def lookup(recipient,amount,start,end):
            seen.append((recipient,amount,start,end))
            return [fixture.TX_HASH]
        self.assertEqual(reconcile_commercial_intent_from_candidates(
            pk,42,server_lookup=lookup,pair=self.pair()),"paid")
        self.assertEqual(seen[0],(invoice.recipient,invoice.amount_sun,
                                 invoice.issued_at,invoice.expires_at))
        self.assertEqual(reconcile_commercial_intent_from_candidates(
            pk,42,server_lookup=lookup,pair=self.pair()),"unchanged")
        self.assertEqual(len(seen),1)
        self.assertTrue(commercial_buyer_status(pk,42)["can_download"])
    def test_public_invoice_and_file_are_buyer_only(self):
        from django.test import RequestFactory
        pk,_,_=self.reserve()
        factory=RequestFactory()
        def req(buyer):
            r=factory.get(f"/commerce/trx-easy/invoice/{pk}/",
                          HTTP_HOST="mojplaywin.com",secure=True)
            r.user=SimpleNamespace(pk=buyer,is_authenticated=True,is_active=True)
            return r
        with patch("django.utils.timezone.now",return_value=fixture.NOW+timedelta(seconds=10)):
            rendered=_show_invoice(req(42),pk)
        self.assertEqual(rendered.status_code,200)
        self.assertIn(b"Trust Wallet",rendered.content)
        self.assertIn("Content-Security-Policy",rendered)
        self.assertFalse(json.loads(_invoice_status(req(42),pk).content)["can_download"])
        with self.assertRaises(Http404):
            _download_paid(req(42),pk)
        with self.assertRaises(Http404):
            _show_invoice(req(43),pk)
        self.assertEqual(settle_commercial_intent(pk,fixture.TX_HASH,self.pair()),"paid")
        served=_download_paid(req(42),pk)
        self.assertEqual(served.status_code,200)
        self.assertEqual(b"".join(served.streaming_content),b"PK\x03\x04minimal-test-only-artifact")
        served.close()
        with self.assertRaises(Http404):
            _download_paid(req(43),pk)

if __name__=="__main__":
    unittest.main()
