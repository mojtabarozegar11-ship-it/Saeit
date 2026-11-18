"""Guarded Plan 1 invoice start view; disabled unless every runtime gate is true."""
import json

from django.conf import settings
from django.http import (
    HttpResponseNotAllowed,
    HttpResponseNotFound,
    JsonResponse,
)
from django.views.decorators.csrf import csrf_protect

from .plan1_invoice import REQUIRED_GATES
from .plan1_persistence import persist_plan1_invoice


def _runtime_release_enabled():
    if getattr(settings, "MPW_MOJPROP_PLAN1_ROUTE_ENABLED", False) is not True:
        return False
    if getattr(settings, "MPW_MOJPROP_PLAN1_LIVE_INVOICE_ENABLED", False) is not True:
        return False
    if not getattr(settings, "MPW_MOJPROP_PLAN1_RECIPIENT", ""):
        return False
    if len(getattr(settings, "MPW_MOJPROP_PLAN1_TRUSTED_CONTRACT_SHA256", "")) != 64:
        return False
    return all(
        getattr(settings, "MPW_MOJPROP_PLAN1_" + gate.upper(), False) is True
        for gate in REQUIRED_GATES
    )


@csrf_protect
def start_plan1_invoice(request):
    if not _runtime_release_enabled():
        return HttpResponseNotFound()
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "authenticated buyer required"}, status=401)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"detail": "invalid JSON"}, status=400)

    email = getattr(request.user, "email", "")
    if not email or payload.get("buyer_email") != email:
        return JsonResponse({"detail": "verified account email required"}, status=400)
    if payload.get("buyer_terms_acceptance") is not True:
        return JsonResponse({"detail": "terms acceptance required"}, status=400)
    try:
        invoice = persist_plan1_invoice(
            order_ref=payload.get("order_ref"),
            buyer_email=email,
            buyer_terms_acceptance=True,
            recipient=settings.MPW_MOJPROP_PLAN1_RECIPIENT,
            contract_digest=settings.MPW_MOJPROP_PLAN1_TRUSTED_CONTRACT_SHA256,
        )
    except Exception as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    return JsonResponse(
        {
            "invoice_ref": invoice.order_ref,
            "product": invoice.product_code,
            "network": invoice.network,
            "amount_sun": invoice.amount_sun,
            "status": invoice.status,
        },
        status=201,
    )
