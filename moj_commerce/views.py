"""Private, authenticated buyer downloads + signed machine-to-machine fulfillment.

These routes are NOT included in MojPlayWin's production URLConf. Do not mount
until a merchant-owned TRON address verification and a SolidityNode proof checker
are installed and the owner approves the release.
"""
import re
from django.conf import settings
from django.core import signing
from django.db import transaction, IntegrityError
from django.http import FileResponse, Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from .models import Entitlement, Purchase
from .private_files import open_verified_product
from .services import CommerceRejected, CommerceUnavailable, finalize_signed_purchase
from mpw_tron_pro.store_delivery import DeliveryUnavailable

TOKEN_SALT = 'moj-commerce-v1-private-download'
DOWNLOAD_TTL_SECONDS = 300
SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}\.zip$')


def _json(data, status=200):
    reply = JsonResponse(data, status=status)
    reply['Cache-Control'] = 'no-store, private'
    reply['Referrer-Policy'] = 'no-referrer'
    reply['X-Content-Type-Options'] = 'nosniff'
    return reply


def _buyer_id(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated or not user.is_active:
        raise Http404
    return user.pk


@csrf_exempt  # HMAC authentication instead of cookie-based CSRF for machine-to-machine webhooks.
@require_POST
def receive_tron_fulfillment(request):
    if getattr(settings, 'MOJ_COMMERCE_RECEIVER_ENABLED', False) is not True:
        return _json({'error': 'receiver_not_enabled'}, 503)
    if request.META.get('CONTENT_TYPE', '').split(';')[0].lower() != 'application/json':
        return _json({'error': 'unsupported_media_type'}, 415)
    if len(request.body) > 4096:
        return _json({'error': 'payload_too_large'}, 413)
    secret = getattr(settings, 'MOJ_COMMERCE_FULFILL_SECRET', '')
    verifier = getattr(settings, 'MOJ_COMMERCE_FINALIZED_TRON_CHECKER', None)
    try:
        receipt = finalize_signed_purchase(request.body,
            request.headers.get('X-MPW-Event-Signature', ''), secret, verifier)
    except CommerceUnavailable:
        return _json({'error': 'chain_verification_unavailable'}, 503)
    except (CommerceRejected, DeliveryUnavailable, IntegrityError):
        return _json({'error': 'fulfillment_rejected'}, 409)
    return _json(receipt)


@require_GET
def buyer_download_link(request, order_ref):
    buyer_id = _buyer_id(request)
    try:
        purchase = Purchase.objects.select_related('product', 'merchant').get(reference=order_ref, buyer_id=buyer_id)
        if purchase.status != Purchase.Status.DELIVERED or not purchase.delivery_id:
            raise Http404
        entitlement = purchase.entitlement
        if entitlement.revoked_at is not None or entitlement.downloads >= entitlement.max_downloads:
            raise Http404
        # A seller suspension also prevents issuing new downloads.
        if purchase.merchant.status != 'approved':
            raise Http404
    except (Purchase.DoesNotExist, Entitlement.DoesNotExist):
        raise Http404
    token = signing.dumps({'e': entitlement.public_id.hex, 'b': buyer_id}, salt=TOKEN_SALT)
    url = reverse('moj-commerce-download', args=(entitlement.public_id, token))
    return _json({'download_url': url, 'valid_for_seconds': DOWNLOAD_TTL_SECONDS,
                  'remaining_downloads': entitlement.max_downloads - entitlement.downloads})


@require_GET
def buyer_download(request, public_id, ticket):
    buyer_id = _buyer_id(request)
    if not isinstance(ticket, str) or len(ticket) > 550:
        raise Http404
    try:
        proof = signing.loads(ticket, salt=TOKEN_SALT, max_age=DOWNLOAD_TTL_SECONDS)
        if (not isinstance(proof, dict) or proof.get('e') != public_id.hex or
            type(proof.get('b')) is not int or proof.get('b') != buyer_id):
            raise Http404
    except (signing.BadSignature, signing.SignatureExpired, ValueError, TypeError):
        raise Http404
    # A fail-safe unique row lock on PostgreSQL. SQLite is for unit tests only.
    with transaction.atomic():
        try:
            entitlement = (Entitlement.objects.select_for_update()
                           .select_related('purchase__product', 'purchase__merchant')
                           .get(public_id=public_id, purchase__buyer_id=buyer_id))
        except Entitlement.DoesNotExist:
            raise Http404
        order = entitlement.purchase
        if (entitlement.revoked_at or entitlement.downloads >= entitlement.max_downloads or
            order.status != Purchase.Status.DELIVERED or not order.delivery_id or
            order.merchant.status != 'approved'):
            raise Http404
        try:
            opened = open_verified_product(order.product)
        except (CommerceRejected, CommerceUnavailable, OSError):
            # Never spend download quota on a missing/corrupt file.
            raise Http404
        entitlement.downloads += 1
        entitlement.save(update_fields=['downloads'])
    filename = order.product.download_name
    if not SAFE_FILENAME.fullmatch(filename):
        filename = 'purchase.zip'
    result = FileResponse(opened, content_type='application/zip', as_attachment=True, filename=filename)
    result['Cache-Control'] = 'no-store, private'
    result['Referrer-Policy'] = 'no-referrer'
    result['X-Content-Type-Options'] = 'nosniff'
    result['X-Frame-Options'] = 'DENY'
    return result