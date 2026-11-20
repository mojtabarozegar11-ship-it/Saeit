"""Internal-only staging identity and login/recovery endpoints.

These endpoints are not a public product surface. They are registered only when
the deployment explicitly enables the staging route, requires the dedicated
MOJ PROP database alias, and presents both a loopback/trusted source address
and a private token. No email, invoice, payment, broker account, or payout is
created here.
"""

import hmac
import json

from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .simulation_identity_adapter import (
    IdentityAdapterClosed,
    activate_identity,
    consume_login_challenge,
    issue_login_challenge,
    register_identity,
)


def _guard(request):
    if not getattr(settings, "MPW_MOJPROP_STAGING_IDENTITY_ROUTE_ENABLED", False):
        raise Http404
    if not getattr(settings, "MPW_MOJPROP_DB_ALIAS_ENABLED", False):
        raise Http404
    if getattr(settings, "MPW_MOJPROP_DEPLOYMENT_ENV", "") != "staging":
        raise Http404
    configured = getattr(settings, "MPW_MOJPROP_STAGING_ROUTE_TOKEN", "")
    supplied = request.headers.get("X-MOJPROP-STAGING-TOKEN", "")
    remote_addr = request.META.get("REMOTE_ADDR", "")
    allowed_ips = tuple(getattr(settings, "MPW_MOJPROP_STAGING_INTERNAL_IPS", ()))
    if (
        not isinstance(configured, str)
        or len(configured) < 32
        or not isinstance(supplied, str)
        or not hmac.compare_digest(configured, supplied)
        or remote_addr not in allowed_ips
    ):
        raise Http404


def _payload(request):
    try:
        value = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise IdentityAdapterClosed("JSON body is required") from None
    if type(value) is not dict:
        raise IdentityAdapterClosed("JSON object is required")
    return value


def _integer(value, label):
    if type(value) is not int or value < 1:
        raise IdentityAdapterClosed(f"{label} is required")
    return value


def _failure(error):
    return JsonResponse(
        {"ok": False, "error": str(error)},
        status=400,
        headers={"Cache-Control": "no-store"},
    )


@csrf_exempt
@require_POST
def staging_identity_register(request):
    try:
        _guard(request)
        data = _payload(request)
        identity_id = register_identity(data.get("email"))
        return JsonResponse(
            {"ok": True, "identity_id": identity_id},
            status=201,
            headers={"Cache-Control": "no-store"},
        )
    except (IdentityAdapterClosed, TypeError, ValueError) as error:
        return _failure(error)


@csrf_exempt
@require_POST
def staging_identity_activate(request):
    try:
        _guard(request)
        data = _payload(request)
        activate_identity(
            _integer(data.get("identity_id"), "identity_id"),
            verification_ref=data.get("verification_ref"),
        )
        return JsonResponse(
            {"ok": True},
            headers={"Cache-Control": "no-store"},
        )
    except (IdentityAdapterClosed, TypeError, ValueError, LookupError) as error:
        return _failure(error)


@csrf_exempt
@require_POST
def staging_identity_challenge(request):
    try:
        _guard(request)
        data = _payload(request)
        issued = issue_login_challenge(
            _integer(data.get("identity_id"), "identity_id"),
            purpose=data.get("purpose", "login"),
        )
        # The code is never returned by HTTP. Delivery is a separate private,
        # authenticated boundary and is intentionally not implemented here.
        return JsonResponse(
            {
                "ok": True,
                "challenge_ref": issued.challenge_ref,
                "expires_at": issued.expires_at.isoformat(),
                "delivery": "private-external-boundary-required",
            },
            headers={"Cache-Control": "no-store"},
        )
    except (IdentityAdapterClosed, TypeError, ValueError, LookupError) as error:
        return _failure(error)


@csrf_exempt
@require_POST
def staging_identity_consume(request):
    try:
        _guard(request)
        data = _payload(request)
        identity_id = consume_login_challenge(
            data.get("challenge_ref"),
            data.get("code"),
        )
        return JsonResponse(
            {"ok": True, "identity_id": identity_id},
            headers={"Cache-Control": "no-store"},
        )
    except (IdentityAdapterClosed, TypeError, ValueError, LookupError) as error:
        return _failure(error)
