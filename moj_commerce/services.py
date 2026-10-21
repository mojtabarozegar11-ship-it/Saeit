"""MOJ Commerce: fail-closed transactional delivery bound to a finalized TRON proof.

Called only by a signed *backend-to-backend* TRON Autopilot event. Independent
mainnet solidity proof must be provided by a trusted operator-configured checker;
no signed message by itself can create an entitlement.
"""
import re
import uuid
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from mpw_tron_pro.store_receiver_contract import verify_store_event
from .models import Merchant, Purchase, Entitlement, MerchantAddress

FILE_KEY = re.compile(r'^[a-f0-9]{32}$')
SHA256 = re.compile(r'^[a-f0-9]{64}$')
ORDER_ID = re.compile(r'^[a-zA-Z0-9_-]{10,80}$')


class CommerceRejected(Exception):
    pass


class CommerceUnavailable(Exception):
    pass


def _validate_existing_purchase(purchase):
    # Invoice price is immutable; a later product reprice must not strand paid buyers.
    if (getattr(settings, 'MOJ_COMMERCE_REQUIRE_SIGNED_WALLET', True) and
        purchase.destination.verified_via != MerchantAddress.ProofMethod.SIGN_V2):
        raise CommerceRejected('Merchant must prove control of destination using TRON signMessageV2')
    if (purchase.merchant.status != Merchant.Status.APPROVED
        or purchase.product.merchant_id != purchase.merchant_id
        or purchase.destination.merchant_id != purchase.merchant_id
        or purchase.destination.verified_at is None
        or purchase.usd_amount <= 0
        or purchase.network != 'tron-mainnet'
        or not FILE_KEY.fullmatch(purchase.product.file_key)
        or not SHA256.fullmatch(purchase.product.sha256)
        or not purchase.product.active):
        raise CommerceRejected('Merchant, source file, or destination not eligible')


def validate_proof(proof, purchase, event):
    """Checker MUST independently read solidified TRON body + execution receipt.

    It must return exactly the committed destination, amount, txid and network;
    any other result fails closed. A unit-test mock is not production evidence.
    """
    if not isinstance(proof, dict) or type(proof.get('confirmed')) is not bool or not proof['confirmed']:
        raise CommerceUnavailable('Independent chain confirmation missing')
    expected = {
        'destination': purchase.destination.address,
        'amount_sun': purchase.amount_sun,
        'txid': event['txid'],
        'network': 'tron-mainnet',
        'block_number': event['block_number'],
    }
    if set(proof) != set(expected) | {'confirmed'} or any(proof.get(k) != v or type(proof.get(k)) is not type(v) for k, v in expected.items()):
        raise CommerceRejected('Independent chain proof differs from order')


def finalize_signed_purchase(raw: bytes, signature: str, secret: str, verifier):
    if not callable(verifier):
        raise CommerceUnavailable('Independent TRON verifier not installed')
    # This reuses the existing branch contract, including signature, duplicate
    # JSON key rejection and strict field schemas.
    event = verify_store_event(raw, signature, secret)
    try:
        snapshot = Purchase.objects.select_related('merchant', 'product', 'destination').get(reference=event['order_id'])
    except Purchase.DoesNotExist as exc:
        raise CommerceRejected('Unknown order') from exc

    _validate_existing_purchase(snapshot)
    if snapshot.amount_sun != event['amount_sun']:
        raise CommerceRejected('Payment amount does not match the locked quote')
    if snapshot.expires_at < snapshot.created_at:
        raise CommerceRejected('Corrupt quote time window')
    event_time = datetime.fromtimestamp(event['paid_ms'] / 1000, dt_timezone.utc)
    if not snapshot.created_at <= event_time <= snapshot.expires_at:
        raise CommerceRejected('Payment outside locked invoice window')

    # The network call runs OUTSIDE the row lock; the order is revalidated under
    # the transaction. The checker must reject any unsolidified or failed receipt.
    verified = verifier(event, snapshot)
    validate_proof(verified, snapshot, event)

    with transaction.atomic():
        purchase = (Purchase.objects.select_for_update()
                    .select_related('merchant', 'product', 'destination')
                    .get(pk=snapshot.pk))
        _validate_existing_purchase(purchase)
        if (purchase.amount_sun != event['amount_sun']
            or purchase.destination_id != snapshot.destination_id
            or purchase.product_id != snapshot.product_id
            or purchase.buyer_id != snapshot.buyer_id
            or purchase.expires_at != snapshot.expires_at):
            raise CommerceRejected('Order changed while verifying chain proof')
        if purchase.status == Purchase.Status.DELIVERED:
            if (purchase.confirmed_txid != event['txid'] or
                purchase.fulfillment_event_id != event['event_id'] or
                not purchase.delivery_id):
                raise CommerceRejected('Conflicting settlement replay')
            ent = Entitlement.objects.get(purchase=purchase)
            return dict(status='delivered', event_id=event['event_id'],
                        order_id=purchase.reference, delivery_id=str(purchase.delivery_id))
        if purchase.status != Purchase.Status.PENDING or purchase.confirmed_txid or purchase.fulfillment_event_id:
            raise CommerceRejected('Order not eligible for settlement')
        # Unique constraints on txid and event_id reject cross-order replays.
        purchase.confirmed_txid = event['txid']
        purchase.fulfillment_event_id = event['event_id']
        purchase.delivery_id = uuid.uuid4()
        purchase.paid_at = event_time
        purchase.delivered_at = timezone.now()
        purchase.status = Purchase.Status.DELIVERED
        purchase.save(update_fields=['confirmed_txid', 'fulfillment_event_id', 'delivery_id',
                                     'paid_at', 'delivered_at', 'status'])
        Entitlement.objects.create(purchase=purchase)
        return dict(status='delivered', event_id=event['event_id'],
                    order_id=purchase.reference, delivery_id=str(purchase.delivery_id))