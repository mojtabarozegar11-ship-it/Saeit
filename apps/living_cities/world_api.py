"""Authenticated authoritative WebGL gameplay API; never trusts client world state."""
import json
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .server_world import act, snapshot


def denied(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    return None


@require_GET
def world_snapshot(request):
    refusal = denied(request)
    if refusal is not None:
        return refusal
    response = JsonResponse(snapshot(request.user))
    response["Cache-Control"] = "private, no-store"
    return response


@csrf_protect
@require_POST
def world_action(request):
    refusal = denied(request)
    if refusal is not None:
        return refusal
    if len(request.body) > 8192:
        return JsonResponse({"error": "body_too_large"}, status=413)
    try:
        body = json.loads(request.body or b"{}")
        if not isinstance(body, dict):
            raise ValidationError("invalid_request")
        data = act(request.user, body.get("action"), body.get("idempotency_key"))
        response = JsonResponse(data)
        response["Cache-Control"] = "private, no-store"
        return response
    except (ValidationError, ValueError, UnicodeDecodeError, TypeError) as exc:
        if isinstance(exc, ValidationError):
            message = exc.messages[0] if exc.messages else "invalid_action"
        else:
            message = "invalid_request"
        return JsonResponse({"error": message}, status=400)
