"""REAL MODULE-to-module buyer journey with SIMULATED on-chain records.

Checks native TRX invoice ledger -> automatic address discovery -> finalized
payment -> atomic outbox -> signed Django receiver -> buyer ZIP. It DOES NOT
contact mainnet, send funds, assign a customer wallet, or test a real cPanel app.
"""
import hashlib
import io
import json
import tempfile
import zipfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from mpw_tron_pro.core import tron_address_hex
from mpw_tron_pro.ledger import InvoiceLedger
from mpw_tron_pro.reconcile import reconcile_pending
from mpw_tron_pro.store_delivery import drain_outbox, send_to_store
from moj_commerce.models import Merchant, MerchantAddress, DigitalProduct, Purchase, Entitlement
from moj_commerce.tron_verifier import independently_verify_finalized_trx

SECRET = 'isolated-gateway-to-django-receiver-' + 'Q'*48
TXID = 'c'*64
ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


def address_from_seed(n):
    raw = bytes.fromhex('41' + f'{n:040x}')
    checksum = hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
    value = int.from_bytes(raw+checksum,'big')
    result = ''
    while value:
        value, digit = divmod(value,58)
        result = ALPHABET[digit] + result
    return result


class DjangoResponseAdapter:
    """Test-only in-process HTTPS response adapter. Never used for live HTTP."""
    def __init__(self, response):
        self.response = response
        self.status = response.status_code
        self.headers = response.headers
    def read(self, limit):
        return self.response.content[:limit]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


@override_settings(
    MOJ_COMMERCE_RECEIVER_ENABLED=True,
    MOJ_COMMERCE_FULFILL_SECRET=SECRET,
    MOJ_COMMERCE_REQUIRE_SIGNED_WALLET=False,  # test-only; production default is True
)
class GatewayToPrivateDeliveryTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='moj-e2e-synthetic-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.file_root = root / 'private'
        self.file_root.mkdir(mode=0o700)
        self.ledger = InvoiceLedger(root/'invoices.sqlite3')
        self.ledger.initialize()
        self.address = address_from_seed(123)
        self.source_address = address_from_seed(456)
        self.ledger.add_public_address(self.address)
        User = get_user_model()
        seller = User.objects.create_user('integration-seller')
        self.buyer = User.objects.create_user('integration-buyer')
        self.other_buyer = User.objects.create_user('integration-other-buyer')
        self.merchant = Merchant.objects.create(name='Integration Seller', owner=seller, status='approved')
        self.destination = MerchantAddress.objects.create(
            merchant=self.merchant, address=self.address, verified_at=timezone.now())
        seller_root = self.file_root / self.merchant.public_id.hex
        seller_root.mkdir(mode=0o700)
        self.file_key = '8'*32
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('hello.txt','A verified delivery from synthetic payment.')
        self.contents = buffer.getvalue()
        (seller_root / (self.file_key+'.zip')).write_bytes(self.contents)
        self.product = DigitalProduct.objects.create(
            merchant=self.merchant,sku='E2E-ZIP',title='Trial ZIP', price_usd=Decimal('4.00'),
            file_key=self.file_key,sha256=hashlib.sha256(self.contents).hexdigest(),active=True)
        self.order_ref = 'MOJC-E2E-abcdef1234'
        self.invoice = self.ledger.issue(
            merchant_order_id=self.order_ref,product_title=self.product.title,
            usd='4.00',usd_per_trx='0.32')
        self.order = Purchase.objects.create(
            reference=self.order_ref,merchant=self.merchant,product=self.product,
            buyer=self.buyer,destination=self.destination,usd_amount=Decimal('4.00'),
            amount_sun=self.invoice.amount_sun, expires_at=timezone.now()+timedelta(minutes=8))
        self.block_ms = int((timezone.now()+timedelta(seconds=5)).timestamp()*1000)
        self.raw, self.receipt = self.transaction_records()
        self.finality_reads = 0
        self.proof_override = override_settings(
            MOJ_COMMERCE_PRIVATE_ROOT=str(self.file_root),
            MOJ_COMMERCE_FINALIZED_TRON_CHECKER=self.chain_checker)
        self.proof_override.enable()
        self.addCleanup(self.proof_override.disable)

    def transaction_records(self, *,amount=None,dest=None):
        amount = self.invoice.amount_sun if amount is None else amount
        dest = self.address if dest is None else dest
        body = {'txID':TXID,'ret':[{'contractRet':'SUCCESS'}],
                'raw_data':{'contract':[{'type':'TransferContract','parameter':{
                    'type_url':'type.googleapis.com/protocol.TransferContract',
                    'value':{'to_address':tron_address_hex(dest),
                             'owner_address':tron_address_hex(self.source_address),'amount':amount}}}]}}
        receipt = {'id':TXID,'blockNumber':1234567,'blockTimeStamp':self.block_ms,
                   'receipt':{'result':'SUCCESS'}}
        return body, receipt

    def chain_checker(self,event,purchase):
        self.finality_reads += 1
        return independently_verify_finalized_trx(
            event,purchase,fetch=lambda txid,api_key: (self.raw,self.receipt))

    def reconcile(self):
        return reconcile_pending(self.ledger,
            discover=lambda address,issued_ms,expires_ms,api_key: [TXID],
            fetch=lambda txid,api_key: (self.raw,self.receipt))

    def receiver(self,request,*,timeout):
        # Secure Django endpoint receives exactly the signed payload prepared by
        # the real gateway dispatcher, bypassing NETWORK only in this test.
        result = self.client.post(reverse('moj-commerce-tron-fulfill'),data=request.data,
            content_type='application/json',
            HTTP_X_MPW_EVENT_SIGNATURE=request.get_header('X-mpw-event-signature'))
        return DjangoResponseAdapter(result)

    def deliver(self,event,*,endpoint,secret):
        return send_to_store(event,endpoint=endpoint,secret=secret,opener=self.receiver)

    def drain(self,now_ms=None):
        return drain_outbox(self.ledger,endpoint='https://mojplaywin.com/api/payments/tron/fulfill/',
            secret=SECRET,deliver=self.deliver, now_ms=now_ms)

    def test_full_automatic_confirmed_trx_to_buyer_download_with_replay(self):
        self.assertEqual(self.ledger.by_order(self.order_ref)['status'],'pending')
        result = self.reconcile()
        self.assertEqual(result['settled'],1)
        self.assertEqual(self.order.status,'pending')
        self.assertEqual(self.ledger.delivery_backlog().get('queued'),1)
        delivered = self.drain()
        self.assertEqual(delivered['delivered'],1)
        self.assertEqual(self.finality_reads,1,'Independent chain proof should be read again')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,'delivered')
        self.assertEqual(self.order.confirmed_txid,TXID)
        self.assertEqual(Entitlement.objects.filter(purchase=self.order).count(),1)
        self.assertEqual(self.ledger.delivery_backlog().get('delivered'),1)
        self.client.force_login(self.buyer)
        link = self.client.get(reverse('moj-commerce-download-link',args=(self.order_ref,)))
        self.assertEqual(link.status_code,200)
        response = self.client.get(link.json()['download_url'])
        self.assertEqual(response.status_code,200)
        content = b''.join(response.streaming_content)
        self.assertEqual(content,self.contents)
        self.client.force_login(self.other_buyer)
        self.assertEqual(self.client.get(link.json()['download_url']).status_code,404)
        self.assertEqual(self.drain()['delivered'],0)
        self.assertEqual(Entitlement.objects.count(),1)

    def test_catalog_reprice_does_not_strand_confirmed_invoice(self):
        # A merchant's later price update cannot alter the buyer's locked quote.
        self.assertEqual(self.order.usd_amount, Decimal('4.00'))
        self.assertEqual(self.reconcile()['settled'], 1)
        self.product.price_usd = Decimal('17.00')
        self.product.save(update_fields=['price_usd'])
        self.assertEqual(self.drain()['delivered'], 1)
        self.order.refresh_from_db()
        self.assertEqual(self.order.usd_amount, Decimal('4.00'))
        self.assertEqual(self.order.status, Purchase.Status.DELIVERED)
        self.assertEqual(Entitlement.objects.filter(purchase=self.order).count(), 1)
        self.client.force_login(self.buyer)
        link = self.client.get(reverse('moj-commerce-download-link', args=(self.order_ref,)))
        self.assertEqual(link.status_code, 200)
        download = self.client.get(link.json()['download_url'])
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b''.join(download.streaming_content), self.contents)

    def test_failed_delivery_keeps_queued_event_and_retries_without_duplicate_right(self):
        self.reconcile()
        # Intentionally disable the store; *payment* remains paid but no goods.
        with override_settings(MOJ_COMMERCE_RECEIVER_ENABLED=False):
            result = self.drain(now_ms=1761060000000)
        self.assertEqual(result['retried'],1)
        self.assertFalse(Entitlement.objects.filter(purchase=self.order).exists())
        self.assertEqual(self.ledger.delivery_backlog().get('queued'),1)
        result2 = self.drain(now_ms=1761060100000)
        self.assertEqual(result2['delivered'],1)
        self.assertEqual(Entitlement.objects.filter(purchase=self.order).count(),1)

    def test_unfinalized_receipt_does_not_release_file(self):
        self.raw, self.receipt = self.transaction_records()
        self.receipt = {}
        self.reconcile()
        self.assertNotEqual(self.ledger.by_order(self.order_ref)['status'],'paid')
        self.assertEqual(self.ledger.delivery_backlog().get('queued',0),0)
        self.assertEqual(Entitlement.objects.count(),0)

    def test_wrong_destination_rejected(self):
        self.raw, self.receipt = self.transaction_records(dest=self.source_address)
        self.reconcile()
        self.assertEqual(Entitlement.objects.count(),0)
        self.assertEqual(self.ledger.delivery_backlog().get('queued',0),0)