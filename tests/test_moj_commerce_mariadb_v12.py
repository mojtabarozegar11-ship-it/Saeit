"""MariaDB/MySQL financial concurrency acceptance on disposable GitHub Actions DB.

Never connects to production MariaDB, TRON RPC, or a real wallet.
All blockchain proofs below are deliberately synthetic.
"""
import hashlib
import hmac
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.db import connection, close_old_connections, IntegrityError
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from moj_commerce.models import DigitalProduct, Entitlement, Merchant, MerchantAddress, Purchase, ScannerRun
from moj_commerce.operations import exclusive_scanner, ConcurrentScanner
from moj_commerce.services import CommerceRejected, finalize_signed_purchase

SECRET = 'isolated-mariadb-test-only-' + 'q' * 40
TXID = 'a' * 64
EVENT_ID = 'mpwtr_' + 'f' * 64


def synthetic_confirmed_proof(event, order):
    # This is NOT a real on-chain verifier. Production remains disabled.
    time.sleep(.025)
    return dict(confirmed=True, txid=event['txid'], destination=order.destination.address,
                amount_sun=order.amount_sun, network='tron-mainnet',
                block_number=event['block_number'])


class MariaDBAcceptanceBase(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'mysql':
            self.skipTest('Requires a disposable MySQL/MariaDB CI database')


class MariaDBScannerMutexTests(MariaDBAcceptanceBase):
    def _competing_session(self):
        close_old_connections()
        try:
            try:
                with exclusive_scanner():
                    return 'acquired'
            except ConcurrentScanner:
                return 'blocked'
        finally:
            close_old_connections()

    def test_other_process_cannot_hold_financial_scanner_lock_at_same_time(self):
        with exclusive_scanner():
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertEqual(pool.submit(self._competing_session).result(timeout=10), 'blocked')
        self.assertEqual(self._competing_session(), 'acquired')

    @override_settings(MOJ_COMMERCE_SCANNER_ENABLED=False)
    def test_disabled_scanner_cannot_write_heartbeat(self):
        with self.assertRaises(CommandError):
            call_command('moj_commerce_scan_once', stdout=StringIO())
        self.assertEqual(ScannerRun.objects.count(), 0)

    @override_settings(MOJ_COMMERCE_SCANNER_ENABLED=True,
                       MOJ_COMMERCE_FINALIZED_TRON_CHECKER=synthetic_confirmed_proof,
                       MOJ_COMMERCE_FULFILL_SECRET=SECRET)
    def test_opt_in_scanner_emits_sanitized_counts_without_rpc(self):
        stats = {'scanned': 2, 'fulfilled': 1, 'underpaid': 0, 'overpaid': 0,
                 'manual_review': 0, 'failures': 0}
        with patch('moj_commerce.management.commands.moj_commerce_scan_once.scan_purchases_once',
                   return_value=stats):
            output = StringIO()
            call_command('moj_commerce_scan_once', stdout=output)
            self.assertIn('scanned=2', output.getvalue())
        run = ScannerRun.objects.get()
        self.assertEqual(run.status, 'ok')
        self.assertEqual(run.fulfilled, 1)


@override_settings(MOJ_COMMERCE_RECEIVER_ENABLED=True,
                   MOJ_COMMERCE_REQUIRE_SIGNED_WALLET=False,
                   MOJ_COMMERCE_FULFILL_SECRET=SECRET,
                   MOJ_COMMERCE_FINALIZED_TRON_CHECKER=synthetic_confirmed_proof)
class MariaDBSettlementConcurrencyTests(MariaDBAcceptanceBase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        owner = User.objects.create_user(username='mariadb-merchant')
        buyer = User.objects.create_user(username='mariadb-buyer')
        self.merchant = Merchant.objects.create(owner=owner, name='MariaDB test merchant', status='approved')
        self.product = DigitalProduct.objects.create(
            merchant=self.merchant, sku='CI-LOCK-1', title='Disposable ZIP',
            price_usd=Decimal('4.00'), file_key='d' * 32,
            sha256='c' * 64, active=True)
        self.destination = MerchantAddress.objects.create(
            merchant=self.merchant, address='T'+'C'*33, verified_at=timezone.now())
        self.purchase = Purchase.objects.create(
            reference='MOJC-MARIADB-001', merchant=self.merchant,
            product=self.product, buyer=buyer, destination=self.destination,
            usd_amount=Decimal('4.00'), amount_sun=12000000,
            expires_at=timezone.now() + timedelta(minutes=10))
        self.event = dict(event_id=EVENT_ID, order_id=self.purchase.reference,
                          network='tron-mainnet', currency='TRX', amount_sun=12000000,
                          txid=TXID, block_number=87654321,
                          paid_ms=int((timezone.now()+timedelta(seconds=3)).timestamp()*1000))
        self.raw, self.signature = self._signed(self.event)

    @staticmethod
    def _signed(event):
        raw = json.dumps(event, sort_keys=True, separators=(',', ':')).encode('utf8')
        return raw, 'v1='+hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()

    def _settle_concurrently(self, barrier):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return finalize_signed_purchase(self.raw, self.signature, SECRET, synthetic_confirmed_proof)
        finally:
            close_old_connections()

    def test_parallel_duplicate_callbacks_issue_only_one_entitlement(self):
        barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(self._settle_concurrently, barrier)
            b = pool.submit(self._settle_concurrently, barrier)
            result_a = a.result(timeout=20)
            result_b = b.result(timeout=20)
        self.assertEqual(result_a, result_b)
        self.assertEqual(result_a['status'], 'delivered')
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.confirmed_txid, TXID)
        self.assertEqual(Entitlement.objects.filter(purchase=self.purchase).count(), 1)

    def test_same_trx_txid_cannot_settle_different_invoice(self):
        finalize_signed_purchase(self.raw, self.signature, SECRET, synthetic_confirmed_proof)
        buyer2 = get_user_model().objects.create_user(username='mariadb-buyer-2')
        dest2 = MerchantAddress.objects.create(merchant=self.merchant, address='T'+'D'*33,
                                               verified_at=timezone.now())
        second = Purchase.objects.create(
            reference='MOJC-MARIADB-002', merchant=self.merchant, product=self.product,
            buyer=buyer2, destination=dest2, usd_amount=Decimal('4.00'),
            amount_sun=12000000, expires_at=timezone.now()+timedelta(minutes=10))
        second_event = {**self.event, 'order_id': second.reference,
                        'event_id': 'mpwtr_'+'e'*64}
        raw, signature = self._signed(second_event)
        with self.assertRaises(IntegrityError):
            finalize_signed_purchase(raw, signature, SECRET, synthetic_confirmed_proof)
        second.refresh_from_db()
        self.assertEqual(second.status, Purchase.Status.PENDING)
        self.assertEqual(Entitlement.objects.filter(purchase=second).count(), 0)

    def test_different_confirmed_tx_cannot_credit_already_delivered_order(self):
        finalize_signed_purchase(self.raw, self.signature, SECRET, synthetic_confirmed_proof)
        replay_event = {**self.event, 'txid': 'b'*64, 'event_id': 'mpwtr_'+'d'*64}
        raw, sig = self._signed(replay_event)
        with self.assertRaises(CommerceRejected):
            finalize_signed_purchase(raw, sig, SECRET, synthetic_confirmed_proof)
        self.assertEqual(Entitlement.objects.filter(purchase=self.purchase).count(), 1)


@override_settings(MOJ_COMMERCE_CHECKOUT_ENABLED=True,
                   MOJ_COMMERCE_REQUIRE_FILE_PRESENT=False,
                   MOJ_COMMERCE_REQUIRE_SIGNED_WALLET=True)
class MariaDBBuyerCheckoutConcurrencyTests(MariaDBAcceptanceBase):
    """Atomic address allocation on real disposable MariaDB InnoDB connections."""
    def setUp(self):
        super().setUp()
        from tests.test_moj_commerce_gateway_e2e import address_from_seed
        User = get_user_model()
        owner = User.objects.create_user(username='mariadb-seller-checkout')
        self.buyer1 = User.objects.create_user(username='mariadb-checkout-buyer-one')
        self.buyer2 = User.objects.create_user(username='mariadb-checkout-buyer-two')
        self.seller = Merchant.objects.create(owner=owner, name='Test Checkout', status='approved')
        self.product = DigitalProduct.objects.create(
            merchant=self.seller, sku='TEST-CHECKOUT', title='CI ZIP',
            price_usd=Decimal('4.00'), file_key='e' * 32,
            sha256='b' * 64, active=True)
        self.addr = MerchantAddress.objects.create(
            merchant=self.seller, address=address_from_seed(4242),
            verified_at=timezone.now(), verified_via='tron-sign-v2')

    def _create_order(self, barrier, buyer, key):
        from moj_commerce.checkout import issue_buyer_checkout
        from moj_commerce.services import CommerceUnavailable
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                order, new = issue_buyer_checkout(
                    buyer_id=buyer.pk, merchant_public_id=self.seller.public_id,
                    product_id=self.product.pk, idempotency_key=key,
                    rate_provider=lambda: Decimal('.32'))
                return ('created' if new else 'replayed', order.pk)
            except CommerceUnavailable:
                return ('unavailable', None)
        finally:
            close_old_connections()

    def test_only_one_buyer_can_reserve_single_payout_address(self):
        barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(self._create_order, barrier, self.buyer1, 'mysql-one-'+'a'*20)
            b = pool.submit(self._create_order, barrier, self.buyer2, 'mysql-two-'+'b'*20)
            results = [a.result(timeout=20), b.result(timeout=20)]
        self.assertCountEqual([x[0] for x in results], ['created', 'unavailable'])
        self.assertEqual(Purchase.objects.count(), 1)
        self.assertEqual(Purchase.objects.get().destination_id, self.addr.pk)

    def test_same_buyer_retry_uses_exactly_one_invoice(self):
        barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(self._create_order, barrier, self.buyer1, 'mysql-retry-'+'c'*20)
            b = pool.submit(self._create_order, barrier, self.buyer1, 'mysql-retry-'+'c'*20)
            results = [a.result(timeout=20), b.result(timeout=20)]
        self.assertCountEqual([x[0] for x in results], ['created', 'replayed'])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(Purchase.objects.count(), 1)


class MariaDBStaleHeartbeatRecoveryTests(MariaDBAcceptanceBase):
    """Recovery never touches purchases; --apply must be an explicit opt-in."""
    def test_dry_run_never_changes_stale_heartbeat(self):
        run = ScannerRun.objects.create(started_at=timezone.now()-timedelta(hours=2))
        output = StringIO()
        call_command('moj_commerce_recover_stale', stdout=output)
        self.assertIn('count=1', output.getvalue())
        run.refresh_from_db()
        self.assertEqual(run.status, ScannerRun.Status.RUNNING)

    @override_settings(MOJ_COMMERCE_RECOVERY_ENABLED=True)
    def test_apply_only_closes_stale_heartbeat_under_mariadb_lock(self):
        old = ScannerRun.objects.create(started_at=timezone.now()-timedelta(hours=2))
        fresh = ScannerRun.objects.create()
        call_command('moj_commerce_recover_stale', '--apply', stdout=StringIO())
        old.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(old.status, ScannerRun.Status.FAILED)
        self.assertEqual(old.error_code, 'STALE_RUN_RECOVERED')
        self.assertEqual(fresh.status, ScannerRun.Status.RUNNING)
