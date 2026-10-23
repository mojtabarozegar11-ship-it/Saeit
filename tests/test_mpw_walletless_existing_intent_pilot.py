"""No-migration, no-money test on isolated MariaDB using REAL Django ORM.

Fixtures emulate cPanel model field/uniqueness shapes without touching cPanel.
The tested service is strictly test-prefix-DB guarded until mainnet acceptance.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from django.db import models, connection
from django.conf import settings
from services.mpw_trx_walletless_core import PaymentHold
from services.mpw_walletless_django_test_bridge import TrustedNodePair
from services.mpw_walletless_existing_intent_pilot import (
    PROVIDER, WAITING, _decode, _encode, _key,
    reserve_existing_test_intent, settle_existing_test_intent,
    existing_test_buyer_status, open_existing_test_paid_file,
    reconcile_existing_test_intent_from_candidates,
)

from tests import test_mpw_walletless_real_django_orm_e2e as fixture


class PaymentIntent(models.Model):
    order=models.OneToOneField(fixture.Order,on_delete=models.PROTECT)
    amount=models.DecimalField(max_digits=14,decimal_places=2)
    currency=models.CharField(max_length=10)
    idempotency_key=models.CharField(max_length=128,unique=True)
    status=models.CharField(max_length=30,default="awaiting_approval")
    provider=models.CharField(max_length=50,default="not_configured")
    provider_reference=models.CharField(max_length=200,blank=True,default="")
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:app_label="test_core";db_table="test_mpw_core_paymentintent"


class PaymentWebhookEvent(models.Model):
    provider=models.CharField(max_length=50)
    event_id=models.CharField(max_length=200)
    event_type=models.CharField(max_length=50)
    payment_intent=models.ForeignKey(PaymentIntent,on_delete=models.PROTECT,null=True)
    payload_hash=models.CharField(max_length=128)
    status=models.CharField(max_length=30,default="received")
    processed_at=models.DateTimeField(null=True,blank=True)
    error=models.TextField(blank=True,default="")
    class Meta:
        app_label="test_core"
        db_table="test_mpw_core_paymentwebhookevent"
        constraints=[models.UniqueConstraint(fields=["provider","event_id"],
            name="test_unique_walletless_payment_event")]


class ExistingLedgerEntry(models.Model):
    order=models.ForeignKey(fixture.Order,on_delete=models.PROTECT)
    payment_intent=models.ForeignKey(PaymentIntent,on_delete=models.PROTECT,null=True)
    entry_type=models.CharField(max_length=30)
    amount=models.DecimalField(max_digits=14,decimal_places=2)
    currency=models.CharField(max_length=10)
    reference=models.CharField(max_length=200,unique=True)
    metadata=models.JSONField(default=dict)
    class Meta:app_label="test_core";db_table="test_mpw_existing_ledgerentry"


fixture.fake_core.PaymentIntent=PaymentIntent
fixture.fake_core.PaymentWebhookEvent=PaymentWebhookEvent
fixture.fake_core.LedgerEntry=ExistingLedgerEntry


class ExistingNoDDLWalletlessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.RealDjangoWalletlessTests.setUpClass()
        with connection.schema_editor() as editor:
            editor.create_model(PaymentIntent)
            editor.create_model(PaymentWebhookEvent)
            editor.create_model(ExistingLedgerEntry)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as editor:
            editor.delete_model(ExistingLedgerEntry)
            editor.delete_model(PaymentWebhookEvent)
            editor.delete_model(PaymentIntent)
        fixture.RealDjangoWalletlessTests.tearDownClass()

    def setUp(self):
        for m in (ExistingLedgerEntry,PaymentWebhookEvent,PaymentIntent):
            m.objects.all().delete()
        fixture.RealDjangoWalletlessTests.setUp(self)
        self.order_id=fixture.Order.objects.get().id

    def reserve(self,buyer=42,order_id=None,random_below=lambda upper:0):
        return reserve_existing_test_intent(order_id or self.order_id,buyer,
            rate_provider=lambda:(Decimal("0.30"),fixture.NOW),
            configured_receiver=lambda:fixture.RECIPIENT,
            now=fixture.NOW,random_below=random_below)

    def pair(self,*,solid=True,tx=None):
        intent = PaymentIntent.objects.get(order_id=self.order_id)
        invoice = _decode(intent)
        transaction = tx or fixture.TX_HASH
        return TrustedNodePair("independent-full-node-a","independent-solidity-node-b",
            prove_a=lambda h:fixture.proof("independent-full-node-a",invoice.amount_sun,transaction,solidified=solid),
            prove_b=lambda h:fixture.proof("independent-solidity-node-b",invoice.amount_sun,transaction),
            audited_as_independent=True)

    def test_no_sidecar_tables_ever_used_for_new_reservation(self):
        pk,invoice,created=self.reserve()
        self.assertTrue(created)
        self.assertEqual(invoice.order_id,self.order_id)
        self.assertEqual(PaymentIntent.objects.get(pk=pk).provider,PROVIDER)
        self.assertEqual(PaymentIntent.objects.get(pk=pk).status,WAITING)
        self.assertEqual(self.reserve(),(pk,invoice,False))
        self.assertEqual(invoice.network,"tron-mainnet")
        self.assertEqual(PaymentWebhookEvent.objects.count(),0)
        self.assertEqual(ExistingLedgerEntry.objects.count(),0)

    def test_durable_key_prevents_double_amount_for_two_orders(self):
        pk,a,_=self.reserve()
        order=fixture.Order.objects.create(customer_id=42,total=Decimal("0.03"),status="pending",currency="USD")
        fixture.OrderItem.objects.create(order=order,unit_price=Decimal("0.03"),kind="digital")
        with self.assertRaises(PaymentHold):
            self.reserve(order_id=order.pk)  # fixed entropy always clashes
        self.assertEqual(PaymentIntent.objects.count(),1)
        pk2,b,_=self.reserve(order_id=order.pk,random_below=lambda upper: 1)
        self.assertNotEqual((pk,a.amount_sun),(pk2,b.amount_sun))
        self.assertNotEqual(_key(a.recipient,a.amount_sun),_key(b.recipient,b.amount_sun))

    def test_finalized_two_source_trx_grants_exactly_one_real_product(self):
        pk,invoice,_=self.reserve()
        self.assertEqual(existing_test_buyer_status(pk,42),{"status":"awaiting","can_download":False})
        self.assertEqual(settle_existing_test_intent(pk,fixture.TX_HASH,self.pair()),"paid")
        self.assertEqual(PaymentIntent.objects.get(pk=pk).status,"paid")
        self.assertEqual(fixture.Order.objects.get(pk=self.order_id).status,"paid")
        event=PaymentWebhookEvent.objects.get(provider=PROVIDER,event_id=fixture.TX_HASH)
        record=ExistingLedgerEntry.objects.get(order_id=self.order_id)
        self.assertEqual(record.payment_intent_id,pk)
        self.assertEqual(record.metadata["walletless_receipt_event_id"],event.pk)
        self.assertEqual(record.metadata["evidence_digest"],event.payload_hash)
        self.assertEqual(fixture.CommerceFulfillment.objects.filter(item__order_id=self.order_id,status="ready").count(),1)
        self.assertEqual(existing_test_buyer_status(pk,42),{
            "status":"paid","can_download":True,
            "download_path":f"/commerce/trx-easy/download/{pk}/",
        })
        with self.assertRaises(PaymentHold):existing_test_buyer_status(pk,43)
        with self.assertRaises(PaymentHold):
            settle_existing_test_intent(pk,fixture.TX_HASH,self.pair())
        self.assertEqual(ExistingLedgerEntry.objects.count(),1)

    def test_no_paid_download_if_receipt_or_ledger_is_missing(self):
        pk,_,_=self.reserve()
        settle_existing_test_intent(pk,fixture.TX_HASH,self.pair())
        PaymentWebhookEvent.objects.filter(payment_intent_id=pk).delete()
        self.assertFalse(existing_test_buyer_status(pk,42)["can_download"])
        self.assertEqual(fixture.Order.objects.get(pk=self.order_id).status,"paid")

    def test_download_opens_actual_private_file_only_after_paid_receipt(self):
        pk,_,_=self.reserve()
        with self.assertRaises(PaymentHold):
            open_existing_test_paid_file(pk,42)
        settle_existing_test_intent(pk,fixture.TX_HASH,self.pair())
        with self.assertRaises(PaymentHold):
            open_existing_test_paid_file(pk,43)
        with open_existing_test_paid_file(pk,42) as delivered:
            self.assertEqual(delivered.read(),b"PK\x03\x04minimal-test-only-artifact")
        PaymentWebhookEvent.objects.filter(payment_intent_id=pk).delete()
        with self.assertRaises(PaymentHold):
            open_existing_test_paid_file(pk,42)

    def test_staging_http_invoice_trust_wallet_status_and_private_download(self):
        from services.mpw_walletless_existing_intent_staging_web import (
            _show_invoice,_invoice_status,_reconcile_invoice,_download_paid,
        )
        from django.http import Http404
        request=SimpleNamespace(user=SimpleNamespace(
            pk=42,is_authenticated=True,is_active=True),META={},
            is_secure=lambda:True,get_host=lambda:"staging.test")
        stolen=SimpleNamespace(user=SimpleNamespace(
            pk=43,is_authenticated=True,is_active=True),META={},
            is_secure=lambda:True,get_host=lambda:"staging.test")
        pk,_,_=self.reserve()
        with patch("django.utils.timezone.now",return_value=fixture.NOW+timedelta(seconds=10)):
            response=_show_invoice(request,pk)
        self.assertEqual(response.status_code,200)
        self.assertIn(b"Open in Trust Wallet (TRX)",response.content)
        self.assertIn(b'data-reconcile-url="/commerce/trx-easy/reconcile/',response.content)
        self.assertIn(b'data-csrf-token="',response.content)
        self.assertIn(b"link.trustwallet.com/send?",response.content)
        self.assertIn("Content-Security-Policy",response)
        self.assertFalse(json.loads(_invoice_status(request,pk).content)["can_download"])
        # Read-only GET cannot settle, even if a trusted server event exists.
        with patch.object(settings,"MPW_WALLETLESS_TRX_TEST_STATUS_RECONCILER",
                          lambda i,b:reconcile_existing_test_intent_from_candidates(
                              i,b,server_lookup=lambda *args:[fixture.TX_HASH],pair=self.pair()),
                          create=True):
            self.assertFalse(json.loads(_invoice_status(request,pk).content)["can_download"])
            confirmed=json.loads(_reconcile_invoice(request,pk).content)
            self.assertEqual(confirmed["status"],"paid")
            self.assertTrue(confirmed["can_download"])
        self.assertEqual(ExistingLedgerEntry.objects.count(),1)
        with self.assertRaises(Http404):
            _show_invoice(stolen,pk)
        with self.assertRaises(Http404):
            _download_paid(request,pk)
        self.assertTrue(json.loads(_invoice_status(request,pk).content)["can_download"])
        download=_download_paid(request,pk)
        self.assertEqual(download.status_code,200)
        self.assertEqual(b"".join(download.streaming_content),
            b"PK\x03\x04minimal-test-only-artifact")
        download.close()
        with self.assertRaises(Http404):
            _download_paid(stolen,pk)

    def test_same_mainnet_hash_cannot_grant_to_second_order(self):
        first,_,_=self.reserve()
        settle_existing_test_intent(first,fixture.TX_HASH,self.pair())
        other=fixture.Order.objects.create(customer_id=42,total=Decimal("0.03"),status="pending",currency="USD")
        fixture.OrderItem.objects.create(order=other,unit_price=Decimal("0.03"),kind="digital")
        second,quoted,_=self.reserve(order_id=other.pk,random_below=lambda upper:1)
        pair=TrustedNodePair("provider-a","provider-b",
            prove_a=lambda h:fixture.proof("provider-a",quoted.amount_sun,h),
            prove_b=lambda h:fixture.proof("provider-b",quoted.amount_sun,h),
            audited_as_independent=True)
        with self.assertRaises(PaymentHold):
            settle_existing_test_intent(second,fixture.TX_HASH,pair)
        self.assertEqual(PaymentWebhookEvent.objects.count(),1)
        self.assertEqual(ExistingLedgerEntry.objects.count(),1)
        self.assertEqual(fixture.Order.objects.get(pk=other.pk).status,"pending")

    def test_unfinalized_trx_never_delivers_file(self):
        pk,_,_=self.reserve()
        with self.assertRaises(PaymentHold):
            settle_existing_test_intent(pk,fixture.TX_HASH,self.pair(solid=False))
        self.assertEqual(PaymentWebhookEvent.objects.count(),0)
        self.assertEqual(ExistingLedgerEntry.objects.count(),0)
        self.assertEqual(fixture.CommerceFulfillment.objects.count(),0)
        self.assertEqual(fixture.Order.objects.get(pk=self.order_id).status,"pending")

    def test_real_rpc_parser_connects_to_existing_payment_tables(self):
        """The actual solidity RPC parser, rather than hand-made proof objects,
        must be able to drive the no-DDL Django settlement atomically.
        Network transport stays mocked; no TRX is transferred.
        """
        from services.mpw_tron_independent_solidified_rpc import (
            RpcProvider, hex_to_tron_address, verified_live_pair,
        )
        receiver_hex="41"+"22"*20
        sender_hex="41"+"11"*20
        canonical_receiver=hex_to_tron_address(receiver_hex)
        ms=int((fixture.NOW+timedelta(minutes=1)).timestamp()*1000)
        calls=[]
        with patch.object(fixture,"RECIPIENT",canonical_receiver):
            pk,invoice,_=self.reserve()
            tx_body={"txID":fixture.TX_HASH,"raw_data":{
                "timestamp":ms-3_000,"contract":[{"type":"TransferContract",
                "parameter":{"value":{"owner_address":sender_hex,
                "to_address":receiver_hex,"amount":invoice.amount_sun}}}]},
                "ret":[{"contractRet":"SUCCESS"}]}
            tx_info={"id":fixture.TX_HASH,"blockNumber":70_000_001,
                     "blockTimeStamp":ms,"receipt":{}}
            first=RpcProvider("rpc-a","operator-a","https://node-a.example.org")
            second=RpcProvider("rpc-b","operator-b","https://node-b.example.com")

            def transport(provider,path,txid):
                calls.append((provider.source_id,path,txid))
                if path.endswith("gettransactionbyid"):
                    return json.loads(json.dumps(tx_body))
                return dict(tx_info)

            pair=verified_live_pair(first,second,
                trusted_operator_attestation=True,transport=transport)
            self.assertEqual(settle_existing_test_intent(pk,fixture.TX_HASH,pair),"paid")
            self.assertEqual(len(calls),4)
            self.assertTrue(all(txid==fixture.TX_HASH for _,_,txid in calls))
            self.assertTrue(existing_test_buyer_status(pk,42)["can_download"])
            self.assertEqual(ExistingLedgerEntry.objects.count(),1)

    def test_rpc_disagreement_rolls_back_entire_existing_ledger(self):
        from services.mpw_tron_independent_solidified_rpc import (
            RpcProvider, hex_to_tron_address, verified_live_pair,
        )
        receiver_hex="41"+"22"*20
        sender_hex="41"+"11"*20
        ms=int((fixture.NOW+timedelta(minutes=1)).timestamp()*1000)
        with patch.object(fixture,"RECIPIENT",hex_to_tron_address(receiver_hex)):
            pk,invoice,_=self.reserve()
            body={"txID":fixture.TX_HASH,"raw_data":{
                "timestamp":ms-1_000,"contract":[{"type":"TransferContract",
                "parameter":{"value":{"owner_address":sender_hex,
                "to_address":receiver_hex,"amount":invoice.amount_sun}}}]},
                "ret":[{"contractRet":"SUCCESS"}]}
            info={"id":fixture.TX_HASH,"blockNumber":70_000_001,
                  "blockTimeStamp":ms,"receipt":{}}
            a=RpcProvider("rpc-a","operator-a","https://node-a.example.org")
            b=RpcProvider("rpc-b","operator-b","https://node-b.example.com")

            def transport(provider,path,txid):
                if path.endswith("gettransactionbyid"):
                    return dict(body)
                reply=dict(info)
                if provider.source_id=="rpc-b":
                    reply["blockTimeStamp"]=ms+3_000
                return reply

            pair=verified_live_pair(a,b,trusted_operator_attestation=True,
                                    transport=transport)
            with self.assertRaises(PaymentHold):
                settle_existing_test_intent(pk,fixture.TX_HASH,pair)
            self.assertEqual(ExistingLedgerEntry.objects.count(),0)
            self.assertEqual(PaymentWebhookEvent.objects.count(),0)
            self.assertEqual(fixture.CommerceFulfillment.objects.count(),0)
            self.assertEqual(PaymentIntent.objects.get(pk=pk).status,WAITING)
            self.assertEqual(fixture.Order.objects.get(pk=self.order_id).status,"pending")

    def test_tampered_quote_or_sender_is_not_a_ledger_receipt(self):
        pk,_,_=self.reserve()
        pair=self.pair()
        intent=PaymentIntent.objects.get(pk=pk)
        doc=json.loads(intent.provider_reference)
        doc["sun"]+=1
        intent.provider_reference=json.dumps(doc)
        intent.save(update_fields=["provider_reference"])
        with self.assertRaises(PaymentHold):
            settle_existing_test_intent(pk,fixture.TX_HASH,pair)
        self.assertEqual(ExistingLedgerEntry.objects.count(),0)

    def test_unrelated_pending_legacy_invoice_does_not_block_this_order(self):
        """A waiting signed invoice for another buyer is not a site-wide freeze."""
        other=fixture.Order.objects.create(
            customer_id=57,total=Decimal("0.03"),status="pending",currency="USD")
        legacy=fixture.CommerceInvoice.objects.create(
            order=other,status=fixture.CommerceInvoice.Status.AWAITING)
        pk,invoice,created=self.reserve()
        self.assertTrue(created)
        self.assertEqual(invoice.order_id,self.order_id)
        self.assertEqual(fixture.CommerceInvoice.objects.get(pk=legacy.pk).status,
            fixture.CommerceInvoice.Status.AWAITING)
        self.assertEqual(settle_existing_test_intent(pk,fixture.TX_HASH,self.pair()),"paid")
        self.assertTrue(existing_test_buyer_status(pk,42)["can_download"])
        self.assertEqual(fixture.Order.objects.get(pk=other.pk).status,"pending")
        self.assertEqual(fixture.CommerceInvoice.objects.get(pk=legacy.pk).status,
            fixture.CommerceInvoice.Status.AWAITING)

    def test_server_only_candidate_reconciliation_grants_exactly_one_download(self):
        pk,invoice,_=self.reserve()
        observed=[]
        def server_lookup(recipient,sun,issued,expires):
            observed.append((recipient,sun,issued,expires))
            return [fixture.TX_HASH]
        self.assertEqual(reconcile_existing_test_intent_from_candidates(
            pk,42,server_lookup=server_lookup,pair=self.pair()),"paid")
        self.assertEqual(observed[0],(invoice.recipient,invoice.amount_sun,
                                      invoice.issued_at,invoice.expires_at))
        self.assertTrue(existing_test_buyer_status(pk,42)["can_download"])
        self.assertEqual(reconcile_existing_test_intent_from_candidates(
            pk,42,server_lookup=server_lookup,pair=self.pair()),"unchanged")
        self.assertEqual(len(observed),1)
        self.assertEqual(ExistingLedgerEntry.objects.count(),1)
        self.assertEqual(PaymentWebhookEvent.objects.count(),1)

    def test_untrusted_or_ambiguous_chain_candidates_never_settle(self):
        pk,_,_=self.reserve()
        valid_pair=self.pair()
        alternate="0"*64 if fixture.TX_HASH!="0"*64 else "1"*64
        for candidates in ([fixture.TX_HASH,alternate],["invalid"],[fixture.TX_HASH]*17):
            with self.assertRaises(PaymentHold):
                reconcile_existing_test_intent_from_candidates(
                    pk,42,server_lookup=lambda *args:list(candidates),pair=valid_pair)
        with self.assertRaises(PaymentHold):
            reconcile_existing_test_intent_from_candidates(
                pk,43,server_lookup=lambda *args:[fixture.TX_HASH],pair=valid_pair)
        self.assertEqual(reconcile_existing_test_intent_from_candidates(
            pk,42,server_lookup=lambda *args:[],pair=valid_pair),"awaiting")
        self.assertEqual(ExistingLedgerEntry.objects.count(),0)
        self.assertEqual(PaymentWebhookEvent.objects.count(),0)
        self.assertEqual(fixture.Order.objects.get(pk=self.order_id).status,"pending")

    def test_wrong_owner_legacy_signed_and_live_database_guard(self):
        with self.assertRaises(PaymentHold):self.reserve(buyer=43)
        fixture.CommerceInvoice.objects.create(order_id=self.order_id,status="awaiting")
        with self.assertRaises(PaymentHold):self.reserve()
        self.assertEqual(PaymentIntent.objects.count(),0)
        with self.assertRaises(PaymentHold):
            self.reserve()
        self.assertEqual(PaymentWebhookEvent.objects.count(),0)

    def test_no_unreviewed_public_release_even_if_backend_is_present(self):
        risky=SimpleNamespace(MPW_WALLETLESS_TRX_TEST_ADAPTER=True,
            MPW_COMMERCE_INVOICING_ENABLED=False,
            MPW_WALLETLESS_TRX_PUBLIC_ENABLED=True)
        with self.assertRaises(PaymentHold):
            reserve_existing_test_intent(self.order_id,42,
                rate_provider=lambda:(Decimal("0.30"),fixture.NOW),
                configured_receiver=lambda:fixture.RECIPIENT,
                settings=risky,now=fixture.NOW)


if __name__=="__main__":unittest.main()
