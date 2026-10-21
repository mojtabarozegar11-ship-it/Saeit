"""Real PostgreSQL concurrency for buyer-driven wallet address reservations.

Test skipped unless PostgreSQL. SQLite cannot prove row locking / pool fairness.
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import connection, close_old_connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from moj_commerce.models import Merchant, MerchantAddress, DigitalProduct, Purchase
from moj_commerce.checkout import issue_buyer_checkout
from moj_commerce.services import CommerceUnavailable
from tests.test_moj_commerce_gateway_e2e import address_from_seed


@override_settings(MOJ_COMMERCE_CHECKOUT_ENABLED=True,
                   MOJ_COMMERCE_REQUIRE_FILE_PRESENT=False,
                   MOJ_COMMERCE_REQUIRE_SIGNED_WALLET=True)
class PostgresBuyerReservationTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor!='postgresql':
            self.skipTest('Financial concurrency proof requires real PostgreSQL')
        User=get_user_model()
        owner=User.objects.create_user('checkout-pg-owner')
        self.buyer1=User.objects.create_user('checkout-pg-buyer-1')
        self.buyer2=User.objects.create_user('checkout-pg-buyer-2')
        self.merchant=Merchant.objects.create(owner=owner,name='Concurrently sold ZIP',status='approved')
        self.product=DigitalProduct.objects.create(
            merchant=self.merchant,sku='PG-ZIP',title='Postgres ZIP',
            price_usd=Decimal('4.00'),file_key='c'*32,
            sha256='b'*64,active=True)
        self.addr=MerchantAddress.objects.create(
            merchant=self.merchant,address=address_from_seed(4001),
            verified_at=timezone.now(),verified_via='tron-sign-v2')

    def start(self,barrier,buyer,key):
        close_old_connections()
        barrier.wait(timeout=7)
        try:
            try:
                order,is_new=issue_buyer_checkout(
                    buyer_id=buyer.pk,merchant_public_id=self.merchant.public_id,
                    product_id=self.product.pk,idempotency_key=key,
                    rate_provider=lambda:Decimal('.32'))
                return 'created' if is_new else 'replayed',order.pk
            except CommerceUnavailable:
                return 'no_address',None
        finally:
            close_old_connections()

    def test_two_buyers_never_reserve_same_one_address(self):
        barrier=threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            fa=pool.submit(self.start,barrier,self.buyer1,'checkout-'+'a'*20)
            fb=pool.submit(self.start,barrier,self.buyer2,'checkout-'+'b'*20)
            a,b=fa.result(timeout=20),fb.result(timeout=20)
        self.assertCountEqual([a[0],b[0]],['created','no_address'])
        self.assertEqual(Purchase.objects.count(),1)
        self.assertEqual(Purchase.objects.get().destination_id,self.addr.pk)

    def test_simultaneous_same_idempotency_key_no_duplicate_order(self):
        barrier=threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            fa=pool.submit(self.start,barrier,self.buyer1,'checkout-'+'d'*20)
            fb=pool.submit(self.start,barrier,self.buyer1,'checkout-'+'d'*20)
            a,b=fa.result(timeout=20),fb.result(timeout=20)
        self.assertCountEqual([a[0],b[0]],['created','replayed'])
        self.assertEqual(a[1],b[1])
        self.assertEqual(Purchase.objects.count(),1)