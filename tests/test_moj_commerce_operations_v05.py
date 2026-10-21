"""Isolated owner-level dashboard and fail-closed scanner telemetry tests."""
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from moj_commerce.models import (Merchant, MerchantAddress, DigitalProduct, Purchase,
                                 PurchaseScanState, PaymentDiscrepancy, ScannerRun)
from moj_commerce.operations import (seller_snapshot, scanner_health,
                                     record_scanner_completion)


def fake_final_checker(event, purchase):
    raise AssertionError('Never call real RPC in health tests')


class MerchantDashboardPrivacyTests(TestCase):
    def setUp(self):
        u=get_user_model()
        self.owner=u.objects.create_user('merchant-op-owner')
        self.other=u.objects.create_user('merchant-op-other')
        self.staff=u.objects.create_user('merchant-op-staff', is_staff=True)
        self.admin=u.objects.create_superuser('merchant-op-admin', 'ops@example.invalid','pass')
        self.merchant=Merchant.objects.create(owner=self.owner,name='Tenant Alpha',status='approved')
        self.foreign=Merchant.objects.create(owner=self.other,name='Tenant Beta',status='approved')
        self.product=DigitalProduct.objects.create(
            merchant=self.merchant,sku='A1',title='Seller one downloadable zip',
            file_key='a'*32,sha256='c'*64,active=True,price_usd=Decimal('4.00'))
        foreign_item=DigitalProduct.objects.create(
            merchant=self.foreign,sku='B1',title='Secret Seller Two Zip',
            file_key='b'*32,sha256='d'*64,active=True,price_usd=Decimal('9.00'))
        a=MerchantAddress.objects.create(merchant=self.merchant,address='T'+'A'*33,
                                         verified_via='tron-sign-v2',verified_at=timezone.now())
        self.free=MerchantAddress.objects.create(merchant=self.merchant,address='T'+'B'*33,
                                         verified_via='tron-sign-v2',verified_at=timezone.now())
        MerchantAddress.objects.create(merchant=self.merchant,address='T'+'C'*33,
                                         verified_via='manual',verified_at=timezone.now())
        f=MerchantAddress.objects.create(merchant=self.foreign,address='T'+'D'*33,
                                         verified_via='tron-sign-v2',verified_at=timezone.now())
        self.order=Purchase.objects.create(
            reference='moj-dashboard-alpha-test-ref-01',merchant=self.merchant,
            product=self.product,buyer=self.owner,destination=a,usd_amount=Decimal('4.00'),
            amount_sun=12500000,expires_at=timezone.now()+timedelta(minutes=8))
        PurchaseScanState.objects.create(purchase=self.order,next_scan_ms=0)
        self.foreign_order=Purchase.objects.create(
            reference='moj-dashboard-beta-test-ref-02',merchant=self.foreign,
            product=foreign_item,buyer=self.other,destination=f,usd_amount=Decimal('9.00'),
            amount_sun=28000000,expires_at=timezone.now()+timedelta(minutes=8))
        PaymentDiscrepancy.objects.create(purchase=self.order,txid='1'*64,amount_sun=1,kind='underpaid')
        PaymentDiscrepancy.objects.create(purchase=self.foreign_order,txid='2'*64,amount_sun=2,kind='overpaid')
        self.url=reverse('moj-commerce-merchant-dashboard',args=(self.merchant.public_id,))

    def test_seller_dashboard_counts_only_own_tenant(self):
        self.client.force_login(self.owner)
        response=self.client.get(self.url)
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertEqual(data['totals']['orders'],1)
        self.assertEqual(data['totals']['payment_discrepancies'],1)
        self.assertEqual(data['totals']['available_verified_addresses'],1)
        self.assertEqual(data['totals']['confirmed_sales_usd'],'0.00')
        self.assertEqual(len(data['recent_orders']),1)
        self.assertIn('payment_discrepancy_review_required',data['warnings'])
        self.assertNotIn('Secret Seller Two',response.content.decode())
        self.assertNotIn('T'+'A'*33,response.content.decode())
        self.assertNotIn('1'*64,response.content.decode())
        self.assertNotIn(self.owner.username,response.content.decode())
        self.assertEqual(response['Cache-Control'],'private, no-store')

    def test_cross_tenant_uuid_does_not_grant_access(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code,404)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code,404)  # admin is not owner
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code,404)

    def test_seller_status_and_exhausted_address_are_visible_only_to_owner(self):
        self.order.expires_at=timezone.now()-timedelta(minutes=1)
        self.order.save(update_fields=['expires_at'])
        self.free.verified_at=None
        self.free.save(update_fields=['verified_at'])
        self.merchant.status='suspended'
        self.merchant.save(update_fields=['status'])
        self.client.force_login(self.owner)
        d=self.client.get(self.url).json()
        self.assertEqual(d['totals']['expired_pending'],1)
        self.assertEqual(d['totals']['available_verified_addresses'],0)
        self.assertIn('merchant_not_approved',d['warnings'])
        self.assertIn('address_pool_exhausted',d['warnings'])

    def test_completed_orders_only_contribute_to_revenue(self):
        self.order.status=Purchase.Status.DELIVERED
        self.order.save(update_fields=['status'])
        snapshot=seller_snapshot(self.merchant)
        self.assertEqual(snapshot['totals']['confirmed_sales_usd'],'4.00')
        self.assertEqual(snapshot['totals']['paid_delivered'],1)
        self.assertEqual(snapshot['totals']['pending'],0)

    def test_operator_health_requires_staff_superuser(self):
        url=reverse('moj-commerce-operator-scanner-health')
        self.assertEqual(self.client.get(url).status_code,404)
        for user in (self.owner,self.other,self.staff):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code,404)
        self.client.force_login(self.admin)
        r=self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['status'],'disabled')
        self.assertNotIn(self.order.destination.address,r.content.decode())
        self.assertNotIn(self.order.reference,r.content.decode())
        self.assertNotIn('1'*64,r.content.decode())


@override_settings(MOJ_COMMERCE_SCANNER_ENABLED=True,
                   MOJ_COMMERCE_CHECKOUT_ENABLED=True,
                   MOJ_COMMERCE_FINALIZED_TRON_CHECKER=fake_final_checker,
                   MOJ_COMMERCE_FULFILL_SECRET='health-audit-'+'H'*50)
class ScannerTelemetryTests(TestCase):
    def _healthy_env(self, **kwargs):
        fake_conn=SimpleNamespace(vendor='postgresql')
        return patch('moj_commerce.operations.connection',fake_conn)

    def test_never_run_is_not_healthy(self):
        with self._healthy_env():
            self.assertEqual(scanner_health()['status'],'never_run')

    def test_recent_success_with_no_due_work_is_healthy(self):
        run=ScannerRun.objects.create()
        record_scanner_completion(run,{'scanned':2,'fulfilled':1})
        with self._healthy_env():
            d=scanner_health()
        self.assertEqual(d['status'],'healthy')
        self.assertEqual(d['last_run_fulfilled'],1)
        self.assertEqual(d['last_run_scanned'],2)

    def test_pending_current_scan_is_not_claimed_healthy(self):
        ScannerRun.objects.create()
        with self._healthy_env():
            self.assertEqual(scanner_health()['status'],'running')

    def test_stale_and_failed_runs_trigger_attention(self):
        run=ScannerRun.objects.create(started_at=timezone.now()-timedelta(minutes=15))
        record_scanner_completion(run,{'scanned':1})
        with self._healthy_env():
            self.assertEqual(scanner_health()['status'],'stale')
        run.started_at=timezone.now()
        run.status='failed';run.error_code='SCAN_FAILED'
        run.save(update_fields=['started_at','status','error_code'])
        with self._healthy_env():
            self.assertEqual(scanner_health()['status'],'degraded')

    def test_sqlite_or_missing_verifier_never_mark_healthy(self):
        run=ScannerRun.objects.create()
        record_scanner_completion(run)
        # SQLite cannot acquire advisory locks, so no financial health claim.
        self.assertEqual(scanner_health()['status'],'not_configured')
        with override_settings(MOJ_COMMERCE_FINALIZED_TRON_CHECKER=None):
            with self._healthy_env():
                self.assertEqual(scanner_health()['status'],'not_configured')
        with override_settings(MOJ_COMMERCE_SCANNER_ENABLED=False):
            with self._healthy_env():
                self.assertEqual(scanner_health()['status'],'disabled')

    def test_metrics_are_restricted_and_error_details_not_stored(self):
        r=ScannerRun.objects.create()
        record_scanner_completion(r,{'scanned':1,'failures':3,'underpaid':2,'overpaid':4},failed=True)
        r.refresh_from_db()
        self.assertEqual(r.error_code,'SCAN_FAILED')
        self.assertEqual(r.discrepancies,6)
        self.assertEqual(r.status,ScannerRun.Status.FAILED)
        with self.assertRaises(ValueError):
            record_scanner_completion(r,{'scanned':2})
        second=ScannerRun.objects.create()
        with self.assertRaises(ValueError):
            record_scanner_completion(second,{'scanned':-1})
        second.refresh_from_db()
        self.assertEqual(second.status,ScannerRun.Status.RUNNING)