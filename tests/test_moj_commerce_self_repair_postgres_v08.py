"""PostgreSQL advisory mutex, operator gate, bounded repair and idempotency."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from moj_commerce.models import (
    DigitalProduct, Merchant, MerchantAddress, Purchase, PurchaseScanState,
    PaymentDiscrepancy, Entitlement,
)
from moj_commerce.operations import ConcurrentScanner


class SelfRepairPostgresTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires PostgreSQL')
        self.user = get_user_model().objects.create_user('repair-pg-owner')
        self.merchant = Merchant.objects.create(
            owner=self.user, name='shop', status=Merchant.Status.APPROVED)
        self.product = DigitalProduct.objects.create(
            merchant=self.merchant, sku='fix', title='Digital file',
            price_usd=Decimal('5.00'), file_key='c'*32, sha256='d'*64)

    def make_purchase(self, suffix, *, good_proof=True, expired=False, status='pending'):
        now = timezone.now()
        destination = MerchantAddress.objects.create(
            merchant=self.merchant, address='T'+suffix*33,
            verified_at=now-timedelta(minutes=1),
            verified_via=('tron-sign-v2' if good_proof else 'manual'))
        purchase = Purchase.objects.create(
            reference='repair-pg-'+suffix, merchant=self.merchant, product=self.product,
            buyer=self.user, destination=destination, usd_amount=Decimal('5.00'),
            amount_sun=2000000, status=status,
            expires_at=now + (timedelta(minutes=15) if not expired else -timedelta(seconds=1)))
        return purchase

    def test_dry_run_opt_in_idempotent_and_only_open_valid(self):
        good = self.make_purchase('a')
        bad_proof = self.make_purchase('b', good_proof=False)
        expired = self.make_purchase('c', expired=True)
        marker = self.make_purchase('d')
        marker.confirmed_txid = '1'*64
        marker.save(update_fields=['confirmed_txid'])
        already = self.make_purchase('e')
        PurchaseScanState.objects.create(purchase=already, next_scan_ms=99999)
        delivered = self.make_purchase('f', status=Purchase.Status.DELIVERED)

        stdout = StringIO()
        call_command('moj_commerce_self_repair', stdout=stdout)
        self.assertIn('DRY_RUN', stdout.getvalue())
        self.assertIn('eligible=1', stdout.getvalue())
        self.assertEqual(PurchaseScanState.objects.count(), 1)
        with self.assertRaises(CommandError):
            call_command('moj_commerce_self_repair', apply=True, stdout=StringIO())
        with override_settings(MOJ_COMMERCE_SELF_REPAIR_ENABLED=True):
            stdout = StringIO()
            call_command('moj_commerce_self_repair', apply=True, stdout=stdout)
            self.assertIn('repaired=1', stdout.getvalue())
            call_command('moj_commerce_self_repair', apply=True, stdout=StringIO())
        self.assertEqual(PurchaseScanState.objects.count(), 2)
        self.assertTrue(PurchaseScanState.objects.filter(purchase=good).exists())
        for untouched in (bad_proof, expired, marker, delivered):
            self.assertFalse(PurchaseScanState.objects.filter(purchase=untouched).exists())
        self.assertEqual(Purchase.objects.filter(status=Purchase.Status.DELIVERED).count(), 1)
        self.assertEqual(Entitlement.objects.count(), 0)
        good.refresh_from_db()
        self.assertIsNone(good.paid_at)
        self.assertIsNone(good.confirmed_txid)
        self.assertEqual(good.status, Purchase.Status.PENDING)

    @override_settings(MOJ_COMMERCE_SELF_REPAIR_ENABLED=True)
    def test_never_queues_discrepant_order(self):
        order = self.make_purchase('g')
        PaymentDiscrepancy.objects.create(
            purchase=order, txid='2'*64, kind='underpaid', amount_sun=1)
        call_command('moj_commerce_self_repair', apply=True, stdout=StringIO())
        self.assertEqual(PurchaseScanState.objects.count(), 0)

    @override_settings(MOJ_COMMERCE_SELF_REPAIR_ENABLED=True)
    def test_active_scanner_blocks_repair(self):
        self.make_purchase('h')
        with patch('moj_commerce.management.commands.moj_commerce_self_repair.exclusive_scanner',
                   side_effect=ConcurrentScanner('busy')):
            with self.assertRaises(CommandError):
                call_command('moj_commerce_self_repair', apply=True, stdout=StringIO())
        self.assertEqual(PurchaseScanState.objects.count(), 0)

    @override_settings(MOJ_COMMERCE_SELF_REPAIR_ENABLED=True)
    def test_bound_enforced(self):
        self.make_purchase('i')
        self.make_purchase('j')
        with self.assertRaises(CommandError):
            call_command('moj_commerce_self_repair', apply=True, limit=26,
                         stdout=StringIO())
        call_command('moj_commerce_self_repair', apply=True, limit=1,
                     stdout=StringIO())
        self.assertEqual(PurchaseScanState.objects.count(), 1)
