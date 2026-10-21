"""Authenticated read-only dashboards; never publish finance controls to browser."""
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET
from .models import Merchant
from .operations import seller_snapshot, scanner_health


def _json(data):
    response=JsonResponse(data, json_dumps_params={'ensure_ascii':True})
    response['Cache-Control']='private, no-store'
    response['Referrer-Policy']='no-referrer'
    response['X-Content-Type-Options']='nosniff'
    return response


@require_GET
def merchant_dashboard(request, merchant_id):
    if not request.user.is_authenticated or not request.user.is_active:
        raise Http404
    # Merchant public UUID is NEVER an authorization token. Filter by owner.
    try:
        merchant=Merchant.objects.get(public_id=merchant_id,owner=request.user)
    except Merchant.DoesNotExist:
        raise Http404
    return _json(seller_snapshot(merchant))


@require_GET
def operator_scanner_health(request):
    # Staff status alone is insufficient to expose cross-seller metrics.
    if (not request.user.is_authenticated or not request.user.is_active or
        not request.user.is_staff or not request.user.is_superuser):
        raise Http404
    return _json(scanner_health())