"""Internal staging-only non-payable commerce preview endpoint."""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .staging_commerce_gate import CommerceGateClosed, evaluate_nonpayable_preview
from .staging_identity_views import _failure, _guard, _payload


@csrf_exempt
@require_POST
def staging_commerce_preview(request):
    try:
        _guard(request)
        data = _payload(request)
        result = evaluate_nonpayable_preview(
            product_code=data.get("product_code"),
            country=data.get("country"),
            gates=data.get("gates"),
        )
        return JsonResponse(
            {
                "ok": True,
                "product_code": result.product_code,
                "country": result.country,
                "terms_version": result.terms_version,
                "refund_policy_version": result.refund_policy_version,
                "missing_gates": result.missing_gates,
                "eligible_for_preview": result.eligible_for_preview,
                "payable": False,
                "settlement_allowed": False,
                "public_route_allowed": False,
                "invoice_created": False,
            },
            headers={"Cache-Control": "no-store"},
        )
    except (CommerceGateClosed, TypeError, ValueError) as error:
        return _failure(error)
