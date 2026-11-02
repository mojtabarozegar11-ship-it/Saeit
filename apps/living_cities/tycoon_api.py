"""Authenticated API for the server-authoritative business economy."""
import json

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .crypto_reward import reward_policy
from .tycoon_server import act, gem_pack, snapshot


def _denied(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    return None


def _payload(request):
    if len(request.body) > 8192:
        raise ValidationError("body_too_large")
    try:
        data = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError, TypeError) as exc:
        raise ValidationError("invalid_request") from exc
    if not isinstance(data, dict):
        raise ValidationError("invalid_request")
    return data


def _error(exc):
    message = exc.messages[0] if isinstance(exc, ValidationError) and exc.messages else "invalid_request"
    status = 413 if message == "body_too_large" else 400
    return JsonResponse({"error": message}, status=status)


@require_GET
def tycoon_snapshot(request):
    refusal = _denied(request)
    if refusal is not None:
        return refusal
    response = JsonResponse(snapshot(request.user))
    response["Cache-Control"] = "private, no-store"
    return response


@csrf_protect
@require_POST
def tycoon_action(request):
    refusal = _denied(request)
    if refusal is not None:
        return refusal
    try:
        body = _payload(request)
        response = JsonResponse(act(request.user, body.get("action"), body.get("idempotency_key")))
        response["Cache-Control"] = "private, no-store"
        return response
    except ValidationError as exc:
        return _error(exc)


@csrf_protect
@require_POST
def gem_purchase(request):
    """Fail closed until a real audited MOJ1 receipt verifier is configured."""
    refusal = _denied(request)
    if refusal is not None:
        return refusal
    try:
        pack = gem_pack(_payload(request).get("pack_id"))
    except ValidationError as exc:
        return _error(exc)
    policy = reward_policy()
    response = JsonResponse({
        "error": "moj1_checkout_paused",
        "state": "PAUSED",
        "pack": pack,
        "policy": {
            "contract_address_configured": policy["contract_address_configured"],
            "contract_identity_verified": policy["contract_identity_verified"],
            "independent_audit_verified": policy["independent_audit_verified"],
        },
    }, status=503)
    response["Cache-Control"] = "private, no-store"
    return response
