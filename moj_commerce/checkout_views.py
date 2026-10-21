"""Authenticated checkout endpoints, explicitly disabled until owner authorizes."""
import json
from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from .checkout import checkout_payload, issue_buyer_checkout
from .models import Merchant, Purchase
from .services import CommerceRejected, CommerceUnavailable


def _auth_user(request):
    if not request.user.is_authenticated or not request.user.is_active:
        raise Http404
    return request.user


def _reply(data, status=200):
    response=JsonResponse(data,status=status)
    response['Cache-Control']='no-store, private'
    response['Referrer-Policy']='no-referrer'
    response['X-Content-Type-Options']='nosniff'
    return response


@csrf_protect
@require_POST
def create_buyer_checkout(request, merchant_id, product_id):
    buyer=_auth_user(request)
    if request.META.get('CONTENT_TYPE','').split(';')[0] != 'application/json':
        return _reply({'error':'unsupported_media_type'},415)
    if len(request.body)>512:
        return _reply({'error':'payload_too_large'},413)
    try:
        def no_duplicates(pairs):
            out={}
            for k,v in pairs:
                if k in out: raise ValueError('Duplicate JSON field')
                out[k]=v
            return out
        payload=json.loads(request.body.decode('utf8'),object_pairs_hook=no_duplicates)
        if type(payload) is not dict or set(payload)!={'idempotency_key'}:
            raise ValueError('Invalid payload fields')
    except (ValueError,UnicodeError):
        return _reply({'error':'invalid_checkout_request'},400)
    try:
        purchase,created=issue_buyer_checkout(
            buyer_id=buyer.pk,merchant_public_id=merchant_id,product_id=product_id,
            idempotency_key=payload['idempotency_key'])
    except CommerceRejected:
        return _reply({'error':'checkout_rejected'},409)
    except CommerceUnavailable:
        return _reply({'error':'checkout_unavailable'},503)
    return _reply(checkout_payload(purchase),201 if created else 200)


@require_GET
def buyer_checkout_status(request, order_ref):
    buyer=_auth_user(request)
    # URL reference is not an authorization mechanism: buyer ownership is checked.
    try:
        purchase=(Purchase.objects.select_related('merchant','product','destination')
                  .get(reference=order_ref,buyer=buyer))
    except Purchase.DoesNotExist:
        raise Http404
    result=checkout_payload(purchase)
    result['expired']=(purchase.status==Purchase.Status.PENDING and
                       timezone.now()>purchase.expires_at)
    result['file_ready']=purchase.status==Purchase.Status.DELIVERED
    return _reply(result)