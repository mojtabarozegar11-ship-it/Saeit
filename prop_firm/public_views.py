"""Public, non-financial Moj Prop applicant intake endpoint.

The endpoint records an interest lead only. It never creates an invoice,
checks KYC, enables checkout, places an order, or authorizes trading/payout.
"""
from __future__ import annotations

import json

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .models import PropApplicant
from .public_intake import model_defaults, public_result, screen_applicant

MAX_BODY_BYTES = 8 * 1024


def _payload(request):
    if len(request.body) > MAX_BODY_BYTES:
        return None, "payload_too_large"
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, "invalid_json"
        if not isinstance(payload, dict):
            return None, "invalid_payload"
        return payload, None
    return request.POST.dict(), None


def _failure(blocker: str, status: int) -> JsonResponse:
    return JsonResponse(
        {
            "accepted": False,
            "blockers": [blocker],
            "next_step": "correct_input",
            "checkout_enabled": False,
            "trading_enabled": False,
            "payout_enabled": False,
        },
        status=status,
    )


@require_POST
@csrf_protect
def public_applicant_intake(request):
    payload, error = _payload(request)
    if error:
        return _failure(error, 413 if error == "payload_too_large" else 400)

    raw_risk = payload.get("risk_acknowledged")
    risk_acknowledged = (
        raw_risk is True
        or (type(raw_risk) is str and raw_risk.strip().lower() == "true")
    )
    decision = screen_applicant(
        email=payload.get("email"),
        preferred_language=payload.get("preferred_language", "fa"),
        jurisdiction=payload.get("jurisdiction"),
        source=payload.get("source"),
        consent_version=payload.get("consent_version"),
        risk_disclosure_version=payload.get("risk_disclosure_version"),
        risk_acknowledged=risk_acknowledged,
    )
    if decision.accepted is not True:
        return JsonResponse(public_result(decision), status=400)

    defaults = model_defaults(decision)
    try:
        with transaction.atomic():
            applicant, created = PropApplicant.objects.get_or_create(
                email=defaults["email"],
                defaults=defaults,
            )
    except IntegrityError:
        return _failure("persistence_conflict", 409)

    response = public_result(decision)
    response.update({"persisted": True, "created": created})
    return JsonResponse(response, status=201 if created else 200)
