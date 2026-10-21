"""v0.6 UI isolation, output escaping and command-line alert contract."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from moj_commerce.models import Merchant, DigitalProduct, MerchantAddress, Purchase
from moj_commerce.operational_alerts import assess_scanner_alerts


class MerchantConsoleTests(TestCase):
    def setUp(self):
        user = get_user_model()
        self.owner = user.objects.create_user('console-owner')
        self.stranger = user.objects.create_user('console-stranger')
        self.merchant = Merchant.objects.create(owner=self.owner, name='Alpha', status='approved')
        other = Merchant.objects.create(owner=self.stranger, name='Beta', status='approved')
        self.url = reverse('moj-commerce-merchant-console', args=[self.merchant.public_id])
        product = DigitalProduct.objects.create(
            merchant=self.merchant, sku='safe', title='<script>alert("xss")</script>',
            file_key='e'*32, sha256='f'*64, active=True, price_usd=Decimal('5.00'))
        another = DigitalProduct.objects.create(
            merchant=other, sku='secret', title='FOREIGN_CONFIDENTIAL_PRODUCT',
            file_key='b'*32, sha256='a'*64, active=True, price_usd=Decimal('10.00'))
        for i, (merchant, buyer, p) in enumerate(((self.merchant,self.owner,product),
                                                  (other,self.stranger,another))):
            address = MerchantAddress.objects.create(
                merchant=merchant, address='T'+str(i)*33,
                verified_via='tron-sign-v2', verified_at=timezone.now())
            Purchase.objects.create(
                reference='console-order-'+str(i), merchant=merchant, buyer=buyer,
                product=p, destination=address, usd_amount=p.price_usd,
                amount_sun=12345678, expires_at=timezone.now()+timedelta(minutes=5),
                confirmed_txid=str(i)*64)

    def test_console_owner_only_and_no_sensitive_fields(self):
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        page = response.content.decode()
        self.assertIn('Seller Console', page)
        self.assertIn('console-order-0', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('<script>alert', page)
        self.assertNotIn('FOREIGN_CONFIDENTIAL_PRODUCT', page)
        self.assertNotIn('console-order-1', page)
        self.assertNotIn('T'+str(0)*33, page)
        self.assertNotIn('0'*64, page)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertIn('frame-ancestors', response['Content-Security-Policy'])

    def test_inactive_owner_denied(self):
        self.owner.is_active = False
        self.owner.save()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 404)


class OperationalAlertTests(TestCase):
    def test_fixed_codes_and_severities(self):
        healthy = assess_scanner_alerts({'status': 'healthy'})
        self.assertEqual(healthy['severity'], 'ok')
        self.assertEqual(healthy['codes'], [])
        self.assertFalse(healthy['financial_processing_confirmed'])
        state = assess_scanner_alerts({'status': 'stale',
                                       'orders_with_repeated_scan_failures': 2})
        self.assertEqual(state['severity'], 'critical')
        self.assertIn('scan_retry_exhaustion', state['codes'])
        self.assertFalse(state['automatic_payment_recovery_permitted'])
        self.assertEqual(assess_scanner_alerts({'status': 'disabled'})['severity'], 'paused')

    def test_bad_metrics_fail_closed(self):
        for data in ({'status':'unknown'}, {'status':'healthy','overdue_scans':-1},
                     {'status':'healthy','overdue_scans':'2'}):
            with self.assertRaises(ValueError):
                assess_scanner_alerts(data)

    def test_healthcheck_is_read_only_and_strict_policy(self):
        stdout = StringIO()
        call_command('moj_commerce_healthcheck', stdout=stdout)
        self.assertIn('scanner_disabled', stdout.getvalue())
        # Disabled by policy is a paused state and doesn't trigger false incidents.
        call_command('moj_commerce_healthcheck', strict=True, stdout=StringIO())
        with override_settings(MOJ_COMMERCE_SCANNER_ENABLED=True):
            with self.assertRaises(CommandError):
                call_command('moj_commerce_healthcheck', strict=True, stdout=StringIO())

    def test_recovery_never_falls_back_to_sqlite(self):
        with self.assertRaises(CommandError):
            call_command('moj_commerce_recover_stale', apply=True, stdout=StringIO())
