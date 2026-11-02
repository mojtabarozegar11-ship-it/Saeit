"""Authenticated HTTP endpoints for the Living Cities domain."""
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .crypto_reward import reward_policy
from .models import PhysicalUnit
from .services import (
    city_snapshot, explore_city, harvest_resources, manufacture_units, migrate_city,
    record_delivery, submit_physical_code,
)
from .tycoon_server import grant_product_marketing


def _json(request):
    if len(request.body) > 8192:
        raise ValidationError("body_too_large")
    try:
        data = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        raise ValidationError("invalid_json")
    if not isinstance(data, dict):
        raise ValidationError("json_object_required")
    return data


def _error(exc):
    if isinstance(exc, PermissionDenied):
        return JsonResponse({"error": str(exc)}, status=403)
    if isinstance(exc, ValidationError):
        return JsonResponse({"error": exc.messages[0] if exc.messages else "invalid_request"}, status=400)
    return JsonResponse({"error": "request_failed"}, status=400)


def _auth(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    return None


@require_GET
def moj1_reward_policy(request):
    return JsonResponse(reward_policy())


@require_GET
def realm(request):
    denied = _auth(request)
    if denied:
        return denied
    return JsonResponse(city_snapshot(request.user))


@csrf_protect
@require_POST
def explore(request):
    denied = _auth(request)
    if denied:
        return denied
    try:
        payload = _json(request)
        city = explore_city(request.user, payload.get("name", ""))
        return JsonResponse({"city_id": city.pk, "city_code": city.code, "biome": city.biome}, status=201)
    except (ValidationError, PermissionDenied) as exc:
        return _error(exc)


@csrf_protect
@require_POST
def harvest(request):
    denied = _auth(request)
    if denied:
        return denied
    try:
        payload = _json(request)
        city_id = int(payload["city_id"])
        return JsonResponse(harvest_resources(request.user, city_id))
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"error": "invalid_city_id"}, status=400)
    except (ValidationError, PermissionDenied) as exc:
        return _error(exc)


@csrf_protect
@require_POST
def migrate(request):
    denied = _auth(request)
    if denied:
        return denied
    try:
        data = _json(request)
        destination_id = int(data["destination_id"])
        receipt, repeated = migrate_city(request.user, destination_id, data.get("idempotency_key", ""))
        return JsonResponse({
            "migration_id": receipt.pk,
            "from_city_id": receipt.from_city_id,
            "to_city_id": receipt.to_city_id,
            "replayed": repeated,
        })
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"error": "invalid_destination"}, status=400)
    except (ValidationError, PermissionDenied) as exc:
        return _error(exc)


@csrf_protect
@require_POST
def issue_product_labels(request):
    denied = _auth(request)
    if denied:
        return denied
    try:
        data = _json(request)
        labels = manufacture_units(
            request.user, order_ref=data.get("order_ref", ""),
            order_evidence=data.get("order_evidence", ""),
            sku=data.get("sku", ""), quantity=data.get("quantity"),
        )
        # Secrets appear only in this authenticated response to a staff operator;
        # do not cache it, log it, or expose it in player browsing APIs.
        response = JsonResponse({"labels": labels}, status=201)
        response["Cache-Control"] = "no-store"
        return response
    except (ValidationError, PermissionDenied) as exc:
        return _error(exc)


@csrf_protect
@require_POST
def confirm_product_delivery(request):
    denied = _auth(request)
    if denied:
        return denied
    try:
        data = _json(request)
        unit = record_delivery(request.user, str(data.get("serial", "")), data.get("delivery_evidence", ""))
        return JsonResponse({"serial": unit.serial, "state": unit.status})
    except (ValidationError, PermissionDenied) as exc:
        return _error(exc)


@csrf_protect
@require_POST
def claim_code(request):
    denied = _auth(request)
    if denied:
        return denied
    try:
        data = _json(request)
        claim, repeated = submit_physical_code(request.user, data.get("code", ""))
        marketing = grant_product_marketing(request.user, claim.pk)
        return JsonResponse({
            "claim_id": claim.pk, "state": claim.status,
            "replayed": repeated,
            "marketing": {
                "applied": marketing["applied"],
                "duration_seconds": marketing["duration_seconds"],
                "revision": marketing["revision"],
                "authority": marketing["authority"],
            },
            "crypto_transfer": "NOT_AUTHORIZED",
            "reward_symbol": claim.reward_symbol,
            "reward_network": claim.reward_network,
        }, status=200 if repeated else 201)
    except (ValidationError, PermissionDenied) as exc:
        return _error(exc)

