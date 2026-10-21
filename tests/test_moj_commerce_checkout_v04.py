"""Seller isolation + buyer-created invoice -> automatic synthetic TRX -> actual Django ZIP.

No real chain, money, wallet signature or production database. CI evidence only.
"""
import hashlib
import io
import json
import tempfile
import time
import zipfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from django.utils import timezone
from moj_commerce.checkout import issue_buyer_checkout, checkout_payload
from moj_commerce.models import (Merchant, MerchantAddress, DigitalProduct,
                                 Purchase, PurchaseScanState, PaymentDiscrepancy, Entitlement)
from moj_commerce.scan_purchases import scan_purchases_once, ScanUnavailable
from moj_commerce.services import CommerceRejected, CommerceUnavailable
from moj_commerce.tron_verifier import independently_verify_finalized_trx
from mpw_tron_pro.core import tron_address_hex
from tests.test_moj_commerce_gateway_e2e import address_from_seed

SECRET='isolated-v04-secret-' + 'M'*60
RATE=Decimal('0.32')
TX='b'*64


def constant_rate():
    return RATE


@override_settings(MOJ_COMMERCE_CHECKOUT_ENABLED=True,
                   MOJ_COMMERCE_TRX_RATE_PROVIDER=constant_rate,
                   MOJ_COMMERCE_REQUIRE_SIGNED_WALLET=True,
                   MOJ_COMMERCE_FULFILL_SECRET=SECRET,
                   MOJ_COMMERCE_SCANNER_ENABLED=True,
                   MOJ_COMMERCE_REQUIRE_FILE_PRESENT=True)
class BuyerCheckoutIsolationTests(TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory(prefix='moj-v04-seller-')
        self.addCleanup(root.cleanup)
        self.root=Path(root.name)/'private'
        self.root.mkdir(mode=0o700)
        self.config=override_settings(MOJ_COMMERCE_PRIVATE_ROOT=str(self.root))
        self.config.enable()
        self.addCleanup(self.config.disable)
        U=get_user_model()
        self.owner1=U.objects.create_user('checkout-owner-1')
        self.owner2=U.objects.create_user('checkout-owner-2')
        self.buyer=U.objects.create_user('checkout-buyer')
        self.other=U.objects.create_user('checkout-buyer-other')
        self.a=Merchant.objects.create(owner=self.owner1,name='Seller A',status='approved')
        self.b=Merchant.objects.create(owner=self.owner2,name='Seller B',status='approved')
        self.addr_a1=self.add_addr(self.a,201)
        self.addr_a2=self.add_addr(self.a,202)
        self.addr_b1=self.add_addr(self.b,301)
        self.p_a=self.add_product(self.a,'A-ZIP',Decimal('4.00'),'a'*32)
        self.p_b=self.add_product(self.b,'B-ZIP',Decimal('7.00'),'b'*32)

    def add_addr(self, merchant, seed, *,method='tron-sign-v2'):
        return MerchantAddress.objects.create(merchant=merchant,address=address_from_seed(seed),
                                              verified_at=timezone.now(),verified_via=method)

    def add_product(self, merchant, sku, price, key):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:
            z.writestr('license.txt','Digital product '+sku)
        root=self.root/merchant.public_id.hex
        root.mkdir(mode=0o700,exist_ok=True)
        (root/(key+'.zip')).write_bytes(data.getvalue())
        return DigitalProduct.objects.create(
            merchant=merchant,sku=sku,title=sku,price_usd=price,
            file_key=key,sha256=hashlib.sha256(data.getvalue()).hexdigest(),active=True)

    def purchase(self,merchant=None, product=None, key='checkout-'+ 'x'*20,buyer=None):
        seller=merchant or self.a
        item=product or self.p_a
        return issue_buyer_checkout(buyer_id=(buyer or self.buyer).pk,
            merchant_public_id=seller.public_id,product_id=item.pk,idempotency_key=key)

    def test_isolates_wallets_and_preserves_exact_buyer_invoice(self):
        a,new1=self.purchase()
        b,new2=self.purchase(merchant=self.b,product=self.p_b,key='checkout-'+'y'*20)
        self.assertTrue(new1 and new2)
        self.assertEqual(a.destination.merchant_id,self.a.pk)
        self.assertEqual(b.destination.merchant_id,self.b.pk)
        self.assertNotEqual(a.destination.address,b.destination.address)
        self.assertEqual(a.amount_sun,12_500_000)
        self.assertEqual(b.amount_sun,21_875_000)
        self.assertEqual(PurchaseScanState.objects.count(),2)
        self.assertEqual(checkout_payload(a)['asset'],'TRX')
        self.assertEqual(checkout_payload(b)['amount_trx'],'21.875000')

    def test_idempotency_no_reprice_no_new_address(self):
        first,created=self.purchase()
        self.p_a.price_usd=Decimal('99.00')
        self.p_a.save(update_fields=['price_usd'])
        second,new=self.purchase()
        self.assertTrue(created)
        self.assertFalse(new)
        self.assertEqual(first.pk,second.pk)
        self.assertEqual(second.amount_sun,12_500_000)
        self.assertEqual(Purchase.objects.count(),1)

    def test_address_exhaustion_does_not_cross_merchants(self):
        self.purchase(key='checkout-'+'a'*20)
        self.purchase(key='checkout-'+'b'*20)
        with self.assertRaises(CommerceUnavailable):
            self.purchase(key='checkout-'+'c'*20)
        b,_=self.purchase(merchant=self.b,product=self.p_b,key='checkout-'+'d'*20)
        self.assertEqual(b.destination.merchant_id,self.b.pk)

    def test_foreign_product_cannot_be_purchased_under_wrong_merchant(self):
        with self.assertRaises(CommerceRejected):
            self.purchase(merchant=self.a,product=self.p_b)
        self.assertEqual(Purchase.objects.count(),0)

    def test_manual_address_is_not_sufficient(self):
        self.addr_a1.verified_via='manual'; self.addr_a1.save(update_fields=['verified_via'])
        self.addr_a2.verified_via='manual'; self.addr_a2.save(update_fields=['verified_via'])
        with self.assertRaises(CommerceUnavailable):
            self.purchase()

    def test_suspended_merchant_is_not_allowed(self):
        self.a.status='suspended';self.a.save(update_fields=['status'])
        with self.assertRaises(CommerceRejected):
            self.purchase()

    def test_missing_file_cannot_issue_checkout(self):
        (self.root/self.a.public_id.hex/(self.p_a.file_key+'.zip')).unlink()
        with self.assertRaises((CommerceRejected,CommerceUnavailable,OSError)):
            self.purchase()
        self.assertEqual(Purchase.objects.count(),0)

    def test_bad_quote_is_fail_closed(self):
        with self.assertRaises(CommerceUnavailable):
            issue_buyer_checkout(buyer_id=self.buyer.pk,merchant_public_id=self.a.public_id,
                product_id=self.p_a.pk,idempotency_key='checkout-'+'q'*20,
                rate_provider=lambda: Decimal('0'))

    def test_disabled_checkout_does_not_issue_invoice(self):
        with override_settings(MOJ_COMMERCE_CHECKOUT_ENABLED=False):
            with self.assertRaises(CommerceUnavailable): self.purchase()
        self.assertFalse(Purchase.objects.exists())

    def test_buyer_endpoint_has_no_browser_price_or_wallet_override(self):
        self.client.force_login(self.buyer)
        url=reverse('moj-commerce-buyer-checkout',args=(self.a.public_id,self.p_a.pk))
        raw=json.dumps({'idempotency_key':'checkout-'+'v'*20,'amount_trx':'0.001'})
        self.assertEqual(self.client.post(url,raw,content_type='application/json').status_code,400)
        self.assertFalse(Purchase.objects.exists())
        result=self.client.post(url,json.dumps({'idempotency_key':'checkout-'+'v'*20}),
                                content_type='application/json')
        self.assertEqual(result.status_code,201)
        self.assertEqual(result.json()['amount_sun'],12_500_000)
        self.assertEqual(result.json()['destination'],self.addr_a1.address)
        self.assertEqual(result['Cache-Control'],'no-store, private')

    def test_duplicate_browser_json_field_is_rejected(self):
        self.client.force_login(self.buyer)
        url=reverse('moj-commerce-buyer-checkout',args=(self.a.public_id,self.p_a.pk))
        raw='{"idempotency_key":"'+('v'*20)+'","idempotency_key":"'+('x'*20)+'"}'
        self.assertEqual(self.client.post(url,raw,content_type='application/json').status_code,400)

    def test_cross_buyer_status_is_private(self):
        order,_=self.purchase()
        url=reverse('moj-commerce-checkout-status',args=(order.reference,))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code,404)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(url).status_code,200)

    def test_client_csrf_required_for_actual_order(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.buyer)
        url=reverse('moj-commerce-buyer-checkout',args=(self.a.public_id,self.p_a.pk))
        result=client.post(url,json.dumps({'idempotency_key':'checkout-'+'v'*20}),
                            content_type='application/json')
        self.assertEqual(result.status_code,403)

    def test_auto_scan_from_buyer_invoice_to_authenticated_zip_download(self):
        order,_=self.purchase()
        event_time=int((order.created_at+timedelta(seconds=2)).timestamp()*1000)
        def finalized(txid,api_key=''):
            body={'txID':txid,'ret':[{'contractRet':'SUCCESS'}],
                 'raw_data':{'contract':[{'type':'TransferContract','parameter':{
                     'type_url':'type.googleapis.com/protocol.TransferContract',
                     'value':{'to_address':tron_address_hex(order.destination.address),
                              'owner_address':tron_address_hex(address_from_seed(501)),
                              'amount':order.amount_sun}}}]}}
            receipt={'id':txid,'blockNumber':200001,'blockTimeStamp':event_time,
                     'receipt':{'result':'SUCCESS'}}
            return body,receipt
        read_count=[]
        def checker(event,purchase):
            read_count.append(event['txid'])
            return independently_verify_finalized_trx(event,purchase,fetch=finalized)
        result=scan_purchases_once(
            discover=lambda addr,start,end,api_key:[TX],fetch=finalized,
            verifier=checker,secret=SECRET,
            now_ms=int(time.time()*1000)+5000)
        self.assertEqual(result['fulfilled'],1)
        self.assertEqual(len(read_count),1)
        order.refresh_from_db()
        self.assertEqual(order.status,Purchase.Status.DELIVERED)
        self.assertEqual(Entitlement.objects.filter(purchase=order).count(),1)
        self.client.force_login(self.buyer)
        link=self.client.get(reverse('moj-commerce-download-link',args=(order.reference,)))
        self.assertEqual(link.status_code,200)
        data=self.client.get(link.json()['download_url'])
        self.assertEqual(data.status_code,200)
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(b''.join(data.streaming_content))))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(link.json()['download_url']).status_code,404)

    def test_scanner_is_disabled_without_operator_approval(self):
        self.purchase()
        with override_settings(MOJ_COMMERCE_SCANNER_ENABLED=False):
            with self.assertRaises(ScanUnavailable):
                scan_purchases_once(verifier=lambda a,b:{},secret=SECRET)

    def test_exact_amount_missing_receipt_is_never_delivered(self):
        order,_=self.purchase()
        def finalized(txid,api_key=''):
            return {},{}
        result=scan_purchases_once(discover=lambda a,b,c,api_key:[TX],fetch=finalized,
            verifier=lambda a,b:{},secret=SECRET,now_ms=int(time.time()*1000)+5000)
        self.assertEqual(result['fulfilled'],0)
        self.assertEqual(Entitlement.objects.count(),0)
        order.refresh_from_db();self.assertEqual(order.status,Purchase.Status.PENDING)

    def test_underpayment_goes_to_manual_review_not_delivery(self):
        order,_=self.purchase()
        event_time=int((order.created_at+timedelta(seconds=1)).timestamp()*1000)
        def under(txid,api_key=''):
            body={'txID':txid,'ret':[{'contractRet':'SUCCESS'}],
                  'raw_data':{'contract':[{'type':'TransferContract','parameter':{
                      'value':{'to_address':tron_address_hex(order.destination.address),
                               'owner_address':tron_address_hex(address_from_seed(501)),
                               'amount':order.amount_sun-1}}}]}}
            receipt={'id':txid,'blockNumber':10001,'blockTimeStamp':event_time,
                     'receipt':{'result':'SUCCESS'}}
            return body,receipt
        result=scan_purchases_once(discover=lambda a,b,c,api_key:[TX],fetch=under,
            verifier=lambda a,b:{},secret=SECRET,now_ms=int(time.time()*1000)+5000)
        self.assertEqual(result['underpaid'],1)
        self.assertEqual(PaymentDiscrepancy.objects.count(),1)
        self.assertEqual(Entitlement.objects.count(),0)
        order.refresh_from_db();self.assertEqual(order.status,Purchase.Status.PENDING)