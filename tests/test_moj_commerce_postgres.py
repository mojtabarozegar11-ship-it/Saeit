"""Real database locking acceptance; skipped on SQLite, run with Postgres in CI.

Concurrency safety is a high-stakes boundary: duplicate callbacks must not
create two entitlements and the same txid cannot settle separate orders.
"""
import hashlib
import hmac
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import connection, close_old_connections
from django.test import TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone
from moj_commerce.models import DigitalProduct, Entitlement, Merchant, MerchantAddress, Purchase
from moj_commerce.services import finalize_signed_purchase

SECRET = 'test-only-' + 'Q' * 50
TX = 'f' * 64
EVENT_ID = 'mpwtr_' + 'e'*64


def checker(event, order):
    time.sleep(.03)
    return dict(confirmed=True, destination=order.destination.address,
                txid=event['txid'], amount_sun=order.amount_sun,
                network='tron-mainnet', block_number=event['block_number'])


@override_settings(MOJ_COMMERCE_RECEIVER_ENABLED=True,
                   MOJ_COMMERCE_FULFILL_SECRET=SECRET,
                   MOJ_COMMERCE_FINALIZED_TRON_CHECKER=checker)
class PostgresConcurrencyTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Financial concurrency proof requires PostgreSQL, not SQLite')
        user = get_user_model().objects.create_user(username='concurrent-merchant')
        buyer = get_user_model().objects.create_user(username='concurrent-buyer')
        self.merchant = Merchant.objects.create(name='Concurrent Store', status='approved', owner=user)
        self.product = DigitalProduct.objects.create(
            merchant=self.merchant, sku='CONCURRENT', title='ZIP',
            price_usd=Decimal('4.00'), file_key='d'*32,
            sha256='a'*64, active=True)
        self.addr = MerchantAddress.objects.create(merchant=self.merchant,
                                                  address='T'+'C'*33, verified_at=timezone.now())
        self.order = Purchase.objects.create(
            reference='MOJC-concurrency-001', merchant=self.merchant,
            product=self.product, buyer=buyer, destination=self.addr,
            usd_amount=Decimal('4.00'), amount_sun=12345000,
            expires_at=timezone.now()+timedelta(minutes=5))
        event = dict(event_id=EVENT_ID, order_id=self.order.reference,
                     network='tron-mainnet',currency='TRX',amount_sun=12345000,
                     txid=TX,block_number=987654,paid_ms=int((timezone.now()+timedelta(seconds=3)).timestamp()*1000))
        self.raw=json.dumps(event,sort_keys=True,separators=(',',':')).encode()
        self.sig='v1='+hmac.new(SECRET.encode(),self.raw,hashlib.sha256).hexdigest()

    def _worker(self, barrier):
        close_old_connections()
        barrier.wait(timeout=5)
        try:
            return finalize_signed_purchase(self.raw,self.sig,SECRET,checker)
        finally:
            close_old_connections()

    def test_duplicate_signed_events_are_idempotent_under_true_row_locks(self):
        barrier=threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            a=executor.submit(self._worker,barrier)
            b=executor.submit(self._worker,barrier)
            first=a.result(timeout=15)
            second=b.result(timeout=15)
        self.assertEqual(first,second)
        self.assertEqual(first['status'],'delivered')
        self.assertEqual(Entitlement.objects.filter(purchase=self.order).count(),1)
        self.order.refresh_from_db()
        self.assertEqual(self.order.fulfillment_event_id,EVENT_ID)
        self.assertEqual(self.order.confirmed_txid,TX)

    def test_same_txid_cannot_credit_second_order(self):
        from django.db import IntegrityError
        finalize_signed_purchase(self.raw,self.sig,SECRET,checker)
        other=get_user_model().objects.create_user(username='concurrent-buyer2')
        addr2=MerchantAddress.objects.create(merchant=self.merchant,address='T'+'D'*33,verified_at=timezone.now())
        order2=Purchase.objects.create(reference='MOJC-concurrency-002',merchant=self.merchant,
            product=self.product,buyer=other,destination=addr2,usd_amount=Decimal('4.00'),
            amount_sun=12345000,expires_at=timezone.now()+timedelta(minutes=5))
        event=json.loads(self.raw)
        event['order_id']=order2.reference
        event['event_id']='mpwtr_'+'d'*64
        raw=json.dumps(event,sort_keys=True,separators=(',',':')).encode()
        sig='v1='+hmac.new(SECRET.encode(),raw,hashlib.sha256).hexdigest()
        with self.assertRaises(IntegrityError):
            finalize_signed_purchase(raw,sig,SECRET,checker)
        self.assertFalse(Entitlement.objects.filter(purchase=order2).exists())
        order2.refresh_from_db()
        self.assertEqual(order2.status,Purchase.Status.PENDING)


@override_settings(MOJ_COMMERCE_REQUIRE_SIGNED_WALLET=True)
class PostgresWalletProofConcurrencyTests(TransactionTestCase):
    """Concurrent replay cannot consume a single wallet signature twice."""
    def setUp(self):
        from eth_keys import keys
        from tests.test_moj_commerce_wallet import test_wallet_address, sign_v2
        from moj_commerce.wallet_proof import issue_wallet_challenge
        self.pk = keys.PrivateKey(bytes.fromhex('00'*31+'03'))  # test fixture only
        owner = get_user_model().objects.create_user(username='pg-wallet-seller')
        self.merchant=Merchant.objects.create(owner=owner,name='Postgres wallet',status='pending')
        self.address=MerchantAddress.objects.create(merchant=self.merchant,
            address=test_wallet_address(self.pk))
        self.challenge=issue_wallet_challenge(self.merchant.public_id,self.address.pk,owner.pk)
        self.signature=sign_v2(self.pk,self.challenge['message'])
        self.owner_id=owner.pk

    def _attempt(self,barrier):
        from moj_commerce.wallet_proof import complete_wallet_challenge
        from moj_commerce.services import CommerceRejected
        close_old_connections()
        barrier.wait(timeout=5)
        try:
            try:
                complete_wallet_challenge(self.merchant.public_id,self.address.pk,self.owner_id,
                    self.challenge['challenge_id'],self.signature)
                return 'success'
            except CommerceRejected:
                return 'replay_rejected'
        finally:
            close_old_connections()

    def test_exactly_one_signer_verification_in_real_postgres(self):
        if connection.vendor!='postgresql':self.skipTest('Must use real PostgreSQL')
        barrier=threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as exe:
            tasks=[exe.submit(self._attempt,barrier) for _ in range(2)]
            results=[future.result(timeout=15) for future in tasks]
        self.assertCountEqual(results,['success','replay_rejected'])
        self.address.refresh_from_db()
        self.assertEqual(self.address.verified_via,'tron-sign-v2')