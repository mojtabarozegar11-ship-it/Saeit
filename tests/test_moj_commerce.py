"""Contract tests only: no real wallet, network calls or public deployments."""
import hashlib
import hmac
import io
import json
import os
import tempfile
import uuid
import zipfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from moj_commerce.models import DigitalProduct, Entitlement, Merchant, MerchantAddress, Purchase
from moj_commerce.services import finalize_signed_purchase, CommerceRejected, CommerceUnavailable

SECRET = 'pilot-test-not-production-' + 'm' * 40
TX1 = 'a' * 64
TX2 = 'b' * 64


def good_chain_proof(event, order):
    """SYNTHETIC MOCK; never connect this verifier in production settings."""
    return {
        'confirmed': True,
        'txid': event['txid'],
        'destination': order.destination.address,
        'amount_sun': order.amount_sun,
        'network': 'tron-mainnet',
        'block_number': event['block_number'],
    }


@override_settings(MOJ_COMMERCE_RECEIVER_ENABLED=True,
                   MOJ_COMMERCE_FULFILL_SECRET=SECRET,
                   MOJ_COMMERCE_FINALIZED_TRON_CHECKER=good_chain_proof)
class MojCommerceDeliveryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user('seller-one', password='unused')
        self.buyer = User.objects.create_user('buyer-one', password='unused')
        self.other = User.objects.create_user('different-buyer', password='unused')
        self.owner2 = User.objects.create_user('seller-two', password='unused')
        self.merchant = Merchant.objects.create(owner=self.owner, status='approved', name='Store A')
        self.other_merchant = Merchant.objects.create(owner=self.owner2, status='approved', name='Store B')
        self.storage = tempfile.TemporaryDirectory(prefix='moj-private-')
        self.addCleanup(self.storage.cleanup)
        self.root = Path(self.storage.name)
        (self.root / self.merchant.public_id.hex).mkdir(mode=0o700)
        self.storage_override = override_settings(MOJ_COMMERCE_PRIVATE_ROOT=self.storage.name)
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        self.reference = 'MOJC-a1b2c3d4e5'
        self.file_key = '0f' * 16
        self.zip_bytes = self._zip_bytes()
        self.file = self.root / self.merchant.public_id.hex / (self.file_key + '.zip')
        self.file.write_bytes(self.zip_bytes)
        self.address = MerchantAddress.objects.create(
            merchant=self.merchant, address='T' + ('A' * 33), verified_at=timezone.now())
        self.product = DigitalProduct.objects.create(
            merchant=self.merchant, sku='ZIP-01', title='Digital ZIP',
            price_usd=Decimal('4.00'), file_key=self.file_key,
            sha256=hashlib.sha256(self.zip_bytes).hexdigest(), active=True,
            download_name='quality-package.zip')
        self.order = Purchase.objects.create(
            reference=self.reference, merchant=self.merchant, product=self.product,
            buyer=self.buyer, destination=self.address, usd_amount=Decimal('4.00'),
            amount_sun=12000000, expires_at=timezone.now() + timedelta(minutes=10))

    @staticmethod
    def _zip_bytes():
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('readme.txt', 'Purchased file belongs to buyer.')
        return output.getvalue()

    def event(self, tx=TX1, order=None, amount=12000000, eid=None, paid=None):
        if paid is None:
            paid = int((timezone.now() + timedelta(seconds=5)).timestamp() * 1000)
        return {'event_id': eid or ('mpwtr_' + hashlib.sha256(tx.encode()).hexdigest()),
                'order_id': order or self.reference, 'network': 'tron-mainnet',
                'currency': 'TRX', 'amount_sun': amount, 'txid': tx,
                'block_number': 76543210, 'paid_ms': paid}

    def signed(self, event):
        raw = json.dumps(event, separators=(',', ':'), sort_keys=True).encode('utf8')
        signature = 'v1=' + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
        return raw, signature

    def post_event(self, event, signature=None):
        raw, sig = self.signed(event)
        return self.client.post(reverse('moj-commerce-tron-fulfill'), data=raw,
            content_type='application/json', HTTP_X_MPW_EVENT_SIGNATURE=signature or sig)

    def settle(self):
        response = self.post_event(self.event())
        self.assertEqual(response.status_code, 200, response.content)
        return response

    def test_automatic_receipt_creates_exactly_one_entitlement(self):
        response = self.settle()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'delivered')
        self.assertEqual(self.order.confirmed_txid, TX1)
        self.assertEqual(Entitlement.objects.filter(purchase=self.order).count(), 1)
        self.assertEqual(str(self.order.delivery_id), response.json()['delivery_id'])

    def test_replayed_same_event_is_idempotent(self):
        first = self.settle().json()
        second = self.post_event(self.event())
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), first)
        self.assertEqual(Entitlement.objects.count(), 1)

    def test_invalid_signature_denied(self):
        self.assertEqual(self.post_event(self.event(), signature='v1=' + '0'*64).status_code, 409)
        self.assertEqual(Entitlement.objects.count(), 0)

    def test_disabled_gateway_blocks_payment(self):
        with override_settings(MOJ_COMMERCE_RECEIVER_ENABLED=False):
            self.assertEqual(self.post_event(self.event()).status_code, 503)
        self.assertEqual(Entitlement.objects.count(), 0)

    def test_missing_chain_checker_blocks_payment(self):
        with override_settings(MOJ_COMMERCE_FINALIZED_TRON_CHECKER=None):
            self.assertEqual(self.post_event(self.event()).status_code, 503)
        self.assertEqual(Entitlement.objects.count(), 0)

    def test_false_chain_checker_fails_closed(self):
        with override_settings(MOJ_COMMERCE_FINALIZED_TRON_CHECKER=lambda event, order: {'confirmed': False}):
            self.assertEqual(self.post_event(self.event()).status_code, 503)
        self.assertEqual(Entitlement.objects.count(), 0)

    def test_wrong_amount_fails_closed(self):
        self.assertEqual(self.post_event(self.event(amount=12000001)).status_code, 409)
        self.assertEqual(Entitlement.objects.count(), 0)

    def test_wrong_destination_proof_fails_closed(self):
        bad = lambda event, order: {**good_chain_proof(event, order), 'destination': 'T'+'Z'*33}
        with override_settings(MOJ_COMMERCE_FINALIZED_TRON_CHECKER=bad):
            self.assertEqual(self.post_event(self.event()).status_code, 409)
        self.assertEqual(Entitlement.objects.count(), 0)

    def test_nonfinalized_proof_fails_closed(self):
        bad = lambda event, order: {**good_chain_proof(event, order), 'confirmed': 1}
        with override_settings(MOJ_COMMERCE_FINALIZED_TRON_CHECKER=bad):
            self.assertEqual(self.post_event(self.event()).status_code, 503)

    def test_wrong_order_id_fails_closed(self):
        self.assertEqual(self.post_event(self.event(order='MOJC-nonexistent-123')).status_code, 409)

    def test_suspended_merchant_not_paid(self):
        self.merchant.status = 'suspended'
        self.merchant.save(update_fields=['status'])
        self.assertEqual(self.post_event(self.event()).status_code, 409)

    def test_unverified_wallet_not_paid(self):
        self.address.verified_at = None
        self.address.save(update_fields=['verified_at'])
        self.assertEqual(self.post_event(self.event()).status_code, 409)

    def test_cross_seller_product_not_paid(self):
        self.order.merchant = self.other_merchant
        self.order.save(update_fields=['merchant'])
        self.assertEqual(self.post_event(self.event()).status_code, 409)

    def test_invoice_expired_payment_not_credited(self):
        late = int((self.order.expires_at + timedelta(seconds=60)).timestamp() * 1000)
        self.assertEqual(self.post_event(self.event(paid=late)).status_code, 409)

    def test_untrusted_extra_json_fields_rejected(self):
        self.assertEqual(self.post_event({**self.event(), 'admin': True}).status_code, 409)

    def test_unsigned_payment_browser_alone_cannot_fulfill(self):
        resp = self.client.post(reverse('moj-commerce-tron-fulfill'), self.event(), content_type='application/json')
        self.assertEqual(resp.status_code, 409)

    def test_non_json_content_type_rejected(self):
        self.assertEqual(self.client.post(reverse('moj-commerce-tron-fulfill'),
            data='x', content_type='text/plain').status_code, 415)

    def test_large_payload_rejected(self):
        resp = self.client.post(reverse('moj-commerce-tron-fulfill'),
            data=b'{' + b'A' * 4096, content_type='application/json')
        self.assertEqual(resp.status_code, 413)

    def test_other_user_cannot_see_private_link(self):
        self.settle()
        self.client.force_login(self.other)
        response = self.client.get(reverse('moj-commerce-download-link', args=[self.reference]))
        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_cannot_see_link(self):
        self.settle()
        response = self.client.get(reverse('moj-commerce-download-link', args=[self.reference]))
        self.assertEqual(response.status_code, 404)

    def test_unpaid_buyer_cannot_receive_link(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('moj-commerce-download-link', args=[self.reference]))
        self.assertEqual(response.status_code, 404)

    def _download_url(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('moj-commerce-download-link', args=[self.reference]))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['valid_for_seconds'], 300)
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        return response.json()['download_url']

    def test_paid_buyer_downloads_verified_zip(self):
        self.settle()
        url = self._download_url()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertEqual(b''.join(response.streaming_content), self.zip_bytes)
        self.order.entitlement.refresh_from_db()
        self.assertEqual(self.order.entitlement.downloads, 1)

    def test_download_requires_same_buyer_even_with_stolen_url(self):
        self.settle()
        url = self._download_url()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_download_url_signature_tampering_rejected(self):
        self.settle()
        url = self._download_url()
        self.assertEqual(self.client.get(url[:-1] + ('x' if url[-1] != 'x' else 'y')).status_code, 404)

    def test_download_expiry_rejected(self):
        self.settle()
        url = self._download_url()
        with mock.patch('moj_commerce.views.signing.loads', side_effect=signing.SignatureExpired('Expired')):
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_download_limit_enforced(self):
        self.settle()
        ent = self.order.entitlement
        ent.max_downloads = 1
        ent.save(update_fields=['max_downloads'])
        url = self._download_url()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        b''.join(r.streaming_content)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_download_revoked(self):
        self.settle()
        url = self._download_url()
        ent = self.order.entitlement
        ent.revoked_at = timezone.now()
        ent.save(update_fields=['revoked_at'])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_corrupted_file_does_not_spend_download(self):
        self.settle()
        url = self._download_url()
        self.file.write_bytes(b'altered data')
        self.assertEqual(self.client.get(url).status_code, 404)
        self.order.entitlement.refresh_from_db()
        self.assertEqual(self.order.entitlement.downloads, 0)

    def test_symlink_file_denied(self):
        self.settle()
        url = self._download_url()
        self.file.unlink()
        otherfile = self.root / 'external.zip'
        otherfile.write_bytes(self.zip_bytes)
        self.file.symlink_to(otherfile)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.order.entitlement.refresh_from_db()
        self.assertEqual(self.order.entitlement.downloads, 0)

    def test_store_disabled_blocks_future_downloads(self):
        self.settle()
        url = self._download_url()
        self.merchant.status = 'suspended'
        self.merchant.save(update_fields=['status'])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_filename_header_is_sanitized(self):
        self.settle()
        self.product.download_name = 'unsafe-\r\n.zip'
        self.product.save(update_fields=['download_name'])
        url = self._download_url()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn('purchase.zip', r['Content-Disposition'])
        b''.join(r.streaming_content)

    def test_replayed_payment_for_another_order_rejected(self):
        self.settle()
        new_addr = MerchantAddress.objects.create(merchant=self.merchant, address='T'+'B'*33,
            verified_at=timezone.now())
        p2 = Purchase.objects.create(reference='MOJC-22222different', merchant=self.merchant,
            product=self.product, buyer=self.other, destination=new_addr, usd_amount=Decimal('4.00'),
            amount_sun=12000000, expires_at=timezone.now()+timedelta(minutes=10))
        response = self.post_event(self.event(tx=TX1, order=p2.reference, eid='mpwtr_'+'c'*64))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Entitlement.objects.filter(purchase=p2).count(), 0)

    def test_different_event_cannot_recredit_same_order(self):
        self.settle()
        self.assertEqual(self.post_event(self.event(tx=TX2, eid='mpwtr_'+'d'*64)).status_code, 409)
        self.assertEqual(Entitlement.objects.count(), 1)

    def test_paid_receipt_is_only_returned_for_signed_backends(self):
        resp = self.settle().json()
        self.assertEqual(set(resp), {'status', 'event_id', 'order_id', 'delivery_id'})
        self.assertNotIn('address', resp)
        self.assertNotIn('buyer', resp)