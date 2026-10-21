"""Source-only fail-closed eligibility tests; no network, wallet or payments."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone

from moj_commerce.models import (
    DigitalProduct, Entitlement, Merchant, MerchantAddress, PaymentDiscrepancy,
    Purchase,
)
from moj_commerce.self_repair import scan_repair_eligibility


class SelfRepairEligibilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('repair-owner')
        self.seller = Merchant.objects.create(
            owner=self.user, name='repair merchant', status=Merchant.Status.APPROVED)
        self.product = DigitalProduct.objects.create(
            merchant=self.seller, sku='repair', title='Test file', price_usd=Decimal('5.00'),
            file_key='a'*32, sha256='b'*64)
        self.address = MerchantAddress.objects.create(
            merchant=self.seller, address='T'+'a'*33,
            verified_at=timezone.now()-timedelta(minutes=1),
            verified_via=MerchantAddress.ProofMethod.SIGN_V2)
        self.purchase = Purchase.objects.create(
            reference='repair-open-1', merchant=self.seller, product=self.product,
            buyer=self.user, destination=self.address,
            usd_amount=Decimal('5.00'), amount_sun=1700000,
            expires_at=timezone.now()+timedelta(minutes=15))
        self.now = timezone.now()

    def test_valid_unexpired_order_can_only_be_queued(self):
        self.assertEqual(scan_repair_eligibility(self.purchase, now=self.now), 'eligible')
        self.assertEqual(self.purchase.status, Purchase.Status.PENDING)
        self.assertFalse(hasattr(self.purchase, 'entitlement'))

    def test_rejects_financial_markers_and_expired_invoices(self):
        self.purchase.confirmed_txid = '1'*64
        self.assertEqual(scan_repair_eligibility(self.purchase, now=self.now),
                         'financial_marker_present')
        self.purchase.confirmed_txid = None
        self.purchase.expires_at = self.now
        self.assertEqual(scan_repair_eligibility(self.purchase, now=self.now),
                         'outside_open_invoice')

    def test_rejects_inconsistent_merchant_chain_and_wallet(self):
        self.purchase.network = 'tron-shasta'
        self.assertEqual(scan_repair_eligibility(self.purchase, now=self.now),
                         'invalid_invoice_terms')
        self.purchase.network = 'tron-mainnet'
        self.seller.status = Merchant.Status.SUSPENDED
        self.assertEqual(scan_repair_eligibility(self.purchase, now=self.now),
                         'merchant_not_approved')
        self.seller.status = Merchant.Status.APPROVED
        self.address.verified_via = MerchantAddress.ProofMethod.MANUAL
        self.assertEqual(scan_repair_eligibility(self.purchase, now=self.now),
                         'wallet_proof_invalid')

    def test_rejects_discrepancies_and_existing_entitlements(self):
        PaymentDiscrepancy.objects.create(
            purchase=self.purchase, txid='2'*64, amount_sun=30, kind='underpaid')
        self.assertEqual(scan_repair_eligibility(self.purchase, now=self.now),
                         'manual_financial_review')
        PaymentDiscrepancy.objects.all().delete()
        Entitlement.objects.create(purchase=self.purchase)
        self.assertEqual(scan_repair_eligibility(self.purchase, now=self.now),
                         'manual_financial_review')

    def test_invalid_destination_merchant_detected(self):
        other = Merchant.objects.create(
            owner=self.user, name='stranger', status=Merchant.Status.APPROVED)
        self.address.merchant = other
        self.assertEqual(scan_repair_eligibility(self.purchase, now=self.now),
                         'ownership_mismatch')

    def test_sqlite_never_applies_repairs(self):
        with self.assertRaises(CommandError):
            call_command('moj_commerce_self_repair', apply=True, stdout=StringIO())
