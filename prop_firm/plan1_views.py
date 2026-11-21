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
    if request.get_host().split(":", 1)[0].lower() not in {"mojplaywin.com", "www.mojplaywin.com"} or not request.is_secure():
        return HttpResponseNotFound()
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

    if not isinstance(payload, dict):
        return JsonResponse({"detail": "JSON object required"}, status=400)

    email = getattr(request.user, "email", "")
    if not email or payload.get("buyer_email") != email:
        return JsonResponse({"detail": "verified account email required"}, status=400)
    if payload.get("buyer_terms_acceptance") is not True:
        return JsonResponse({"detail": "terms acceptance required"}, status=400)

    purchase_kind = payload.get("purchase_kind", "first")
    # Client input is not an eligibility attestation. Until a trusted server
    # eligibility lookup is wired, retry requests must fail closed.
    if purchase_kind != "first":
        return JsonResponse({"detail": "server retry eligibility required"}, status=403)
    retry_eligibility_verified = False
    try:
        invoice = persist_plan1_invoice(
            order_ref=payload.get("order_ref"),
            buyer_email=email,
            buyer_terms_acceptance=True,
            recipient=settings.MPW_MOJPROP_PLAN1_RECIPIENT,
            contract_digest=settings.MPW_MOJPROP_PLAN1_TRUSTED_CONTRACT_SHA256,
            purchase_kind=purchase_kind,
            retry_eligibility_verified=retry_eligibility_verified,
        )
    except Exception as exc:
        return JsonResponse({"detail": "invoice could not be created"}, status=400)
    return JsonResponse(
        {
            "invoice_ref": invoice.order_ref,
            "product": invoice.product_code,
            "purchase_kind": invoice.purchase_kind,
            "network": invoice.network,
            "amount_sun": invoice.amount_sun,
            "status": invoice.status,
        },
        status=201,
    )
