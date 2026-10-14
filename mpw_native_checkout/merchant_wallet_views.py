"""Administrator-only ownership UI. Routes are NOT connected to the live site.

No payment endpoints or state changes are exposed. POST + CSRF required.
"""
import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .wallet_ownership import (
    MERCHANT_ADDRESSES, WalletOwnershipError,
    create_merchant_challenge, submit_merchant_proof, proven_assets,
)


def _is_owner(request):
    u = request.user
    return bool(u.is_authenticated and u.is_active and u.is_superuser)


def _json_payload(request):
    if len(request.body) > 1024:
        raise WalletOwnershipError("Request body too large")
    try:
        doc = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise WalletOwnershipError("Invalid JSON")
    if type(doc) is not dict:
        raise WalletOwnershipError("Expected JSON object")
    return doc


@login_required
@csrf_protect
@never_cache
@require_GET
def merchant_wallet_page(request):
    if not _is_owner(request):
        return HttpResponseForbidden("Administrator access only")
    return render(request, "mpw_native_checkout/merchant_wallet_proof.html", {
        "addresses": MERCHANT_ADDRESSES,
        "proofs": proven_assets(),
    })


@login_required
@csrf_protect
@never_cache
@require_POST
def merchant_challenge(request):
    if not _is_owner(request):
        return JsonResponse({"error": "forbidden"}, status=403)
    try:
        data = _json_payload(request)
        if set(data) != {"asset"}:
            raise WalletOwnershipError("Unexpected challenge fields")
        challenge, message = create_merchant_challenge(request.user, data["asset"])
    except WalletOwnershipError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({
        "challenge_id": challenge.pk,
        "network": challenge.asset,
        "address": challenge.address,
        "message": message,
        "expires_at": int(challenge.expires_at.timestamp()),
    })


@login_required
@csrf_protect
@never_cache
@require_POST
def merchant_verify(request):
    if not _is_owner(request):
        return JsonResponse({"error": "forbidden"}, status=403)
    try:
        data = _json_payload(request)
        if set(data) != {"challenge_id", "signature"}:
            raise WalletOwnershipError("Unexpected verification fields")
        asset = submit_merchant_proof(
            request.user, data["challenge_id"], data["signature"],
        )
    except WalletOwnershipError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({
        "verified_asset": asset, "ownership": proven_assets(),
        "checkout_activated": False,
    })
