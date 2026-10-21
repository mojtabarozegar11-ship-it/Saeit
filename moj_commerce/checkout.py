"""Buyer-initiated, merchant-isolated TRX invoices (source only, disabled in prod).

PostgreSQL is the production requirement. Each merchant must own a pool of
individually signed, never-before-used deposit addresses. Reservations are
atomic within the SAME database as purchases. No global gateway wallet pool,
client-supplied price, browser wallet key, or token custody is involved.
"""
from __future__ import annotations
import hashlib
import hmac
import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, transaction, IntegrityError
from django.utils import timezone
from mpw_tron_pro.core import CheckoutError, sun_quote, QUOTE_TTL_MS, tron_address_hex
from .models import Merchant, MerchantAddress, DigitalProduct, Purchase, PurchaseScanState
from .services import CommerceRejected, CommerceUnavailable, FILE_KEY, SHA256
from .private_files import open_verified_product

IDEMPOTENCY = re.compile(r'^[A-Za-z0-9_-]{16,128}$')


def reference_for(buyer_id, merchant_id, product_id, key: str) -> str:
    """A buyer-bound idempotency key; a different store/product has a different ref."""
    if not isinstance(key,str) or not IDEMPOTENCY.fullmatch(key):
        raise CommerceRejected('Use a unique checkout key of 16-128 URL-safe chars')
    message=f'moj-commerce:trx:checkout:v1:{buyer_id}:{merchant_id}:{product_id}:{key}'
    return 'mojc_' + hmac.new(settings.SECRET_KEY.encode(),message.encode(),hashlib.sha256).hexdigest()


def checkout_payload(purchase: Purchase) -> dict:
    active = (getattr(settings, 'MOJ_COMMERCE_CHECKOUT_ENABLED', False) is True and
              purchase.status == Purchase.Status.PENDING and
              purchase.expires_at > timezone.now() and
              purchase.merchant.status == Merchant.Status.APPROVED)
    return {
        'order_id': purchase.reference,
        'merchant_id': str(purchase.merchant.public_id),
        'product_id': purchase.product_id,
        'product_title': purchase.product.title,
        'network': 'tron-mainnet',
        'asset': 'TRX',
        'usd': str(purchase.usd_amount),
        'amount_sun': purchase.amount_sun,
        'amount_trx': f'{Decimal(purchase.amount_sun) / Decimal(1_000_000):.6f}',
        # A stale or blocked invoice must not advertise a payable destination.
        'destination': purchase.destination.address if active else None,
        'payment_enabled': active,
        'expires_at': purchase.expires_at.isoformat(),
        'status': purchase.status,
    }


def _require_file_available(product):
    if getattr(settings, 'MOJ_COMMERCE_REQUIRE_FILE_PRESENT', True):
        opened = open_verified_product(product)
        opened.close()


def issue_buyer_checkout(*, buyer_id: int, merchant_public_id, product_id: int,
                         idempotency_key: str, rate_provider=None) -> tuple[Purchase, bool]:
    """Create or replay an immutable buyer invoice. The rate is SERVER-side.

    The user row is locked to prevent parallel pending-order-limit bypass. A
    MerchantAddress row lock prevents two buyers reserving the same address.
    This service does NOT create a separate SQLite gateway invoice; financial
    attribution is owned by the central Django purchase database.
    """
    if type(buyer_id) is not int or buyer_id <= 0 or type(product_id) is not int or product_id <= 0:
        raise CommerceRejected('Invalid buyer or product')
    # Validate merchant ID without user-controlled SQL or queryset scope.
    try:
        merchant = Merchant.objects.get(public_id=merchant_public_id)
    except (Merchant.DoesNotExist, ValueError, TypeError) as exc:
        raise CommerceRejected('Merchant does not exist') from exc
    ref = reference_for(buyer_id, merchant.pk, product_id, idempotency_key)
    # Replay returns exactly the original quote, never reprices or consumes an address.
    existing = Purchase.objects.select_related('merchant','product','destination').filter(reference=ref).first()
    if existing is not None:
        if existing.buyer_id != buyer_id or existing.merchant_id != merchant.pk or existing.product_id != product_id:
            raise CommerceRejected('Checkout reference collision')
        return existing, False
    if not getattr(settings, 'MOJ_COMMERCE_CHECKOUT_ENABLED', False):
        raise CommerceUnavailable('Buyer checkout is not enabled')
    if not callable(rate_provider):
        rate_provider = getattr(settings, 'MOJ_COMMERCE_TRX_RATE_PROVIDER', None)
    if not callable(rate_provider):
        raise CommerceUnavailable('A trusted server-side TRX quote provider is required')
    try:
        rate = Decimal(str(rate_provider()))
        if not rate.is_finite() or not Decimal('.001') <= rate <= Decimal('100'):
            raise CommerceUnavailable('Unsafe TRX rate')
    except (CheckoutError, TypeError, ValueError, InvalidOperation, OverflowError, OSError, TimeoutError) as exc:
        raise CommerceUnavailable('TRX quote unavailable') from exc
    now = timezone.now()
    try:
        with transaction.atomic():
            # Per-buyer DB lock serializes concurrent requests, even for different keys.
            buyer = get_user_model().objects.select_for_update().get(pk=buyer_id, is_active=True)
            replay = Purchase.objects.select_related('merchant','product','destination').filter(reference=ref).first()
            if replay:
                return replay, False
            seller = Merchant.objects.select_for_update().get(pk=merchant.pk)
            if seller.status != Merchant.Status.APPROVED:
                raise CommerceRejected('Merchant has not been approved')
            product = DigitalProduct.objects.select_for_update().get(pk=product_id, merchant=seller)
            if (not product.active or not FILE_KEY.fullmatch(product.file_key)
                or not SHA256.fullmatch(product.sha256)
                or not product.download_name.lower().endswith('.zip')):
                raise CommerceRejected('The selected ZIP is not eligible for sale')
            _require_file_available(product)
            if Purchase.objects.filter(buyer=buyer, status=Purchase.Status.PENDING,
                                       expires_at__gt=now).count() >= 3:
                raise CommerceRejected('Active checkout limit reached')
            # Don't lock a nullable side of an outer join. PostgreSQL row-level
            # locks + the OneToOne purchase destination constraint are BOTH used.
            addresses = (MerchantAddress.objects.filter(
                merchant=seller, verified_at__isnull=False,
                verified_via=MerchantAddress.ProofMethod.SIGN_V2)
                .exclude(pk__in=Purchase.objects.values('destination_id'))
                .order_by('pk'))
            if connection.features.has_select_for_update_skip_locked:
                addresses = addresses.select_for_update(skip_locked=True)
            elif connection.features.has_select_for_update:
                addresses = addresses.select_for_update()
            address = addresses.first()
            if address is None:
                raise CommerceUnavailable('No unused proven wallet addresses for this seller')
            try:
                tron_address_hex(address.address)
                sun = sun_quote(product.price_usd, rate)
            except CheckoutError as exc:
                raise CommerceRejected('Checkout validation failed') from exc
            created = Purchase.objects.create(
                reference=ref, merchant=seller, product=product, buyer=buyer,
                destination=address, usd_amount=product.price_usd,
                amount_sun=sun, network='tron-mainnet',
                expires_at=now+timedelta(milliseconds=QUOTE_TTL_MS),
            )
            PurchaseScanState.objects.create(purchase=created, next_scan_ms=int(now.timestamp()*1000))
            return created, True
    except (Merchant.DoesNotExist, DigitalProduct.DoesNotExist, get_user_model().DoesNotExist) as exc:
        raise CommerceRejected('Unknown or inactive buyer, seller or product') from exc
    except IntegrityError as exc:
        # No retry with a *different* wallet; caller should request a fresh status
        # after a contested idempotency key. Never expose a partial invoice.
        raise CommerceUnavailable('Concurrent checkout reservation conflicted; retry safely') from exc