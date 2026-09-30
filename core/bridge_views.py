import hashlib
import hmac
import json
import os
import time

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST


def _secret():
    return os.getenv("SAEIT_BRIDGE_SECRET", "").encode("utf-8")


def _authorized(request, raw_body=b""):
    secret = _secret()
    if not secret:
        return False, "bridge_not_configured"

    token = request.headers.get("X-Saeit-Bridge-Token", "")
    if token and hmac.compare_digest(token.encode("utf-8"), secret):
        return True, "token"

    timestamp = request.headers.get("X-Saeit-Timestamp", "")
    signature = request.headers.get("X-Saeit-Signature", "")
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False, "invalid_timestamp"
    if abs(int(time.time()) - ts) > 300:
        return False, "expired_request"
    expected = hmac.new(secret, timestamp.encode("utf-8") + b"." + raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False, "invalid_signature"
    return True, "hmac"


@require_GET
def bridge_health(request):
    configured = bool(_secret())
    return JsonResponse({
        "status": "ok" if configured else "degraded",
        "service": "saeit-internal-bridge",
        "configured": configured,
        "auth": "token-or-hmac-sha256",
        "owner_approval": True,
    }, status=200 if configured else 503)


@csrf_exempt
@require_POST
def bridge_dispatch(request):
    raw = request.body or b""
    allowed, auth_mode = _authorized(request, raw)
    if not allowed:
        return JsonResponse({"status": "denied", "reason": auth_mode}, status=401)
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"status": "error", "reason": "invalid_json"}, status=400)

    action = str(payload.get("action", "")).strip()
    if not action:
        return JsonResponse({"status": "error", "reason": "action_required"}, status=400)

    # Bridge boundary: authenticated requests are accepted here, but execution
    # remains behind the site's existing Master Agent / Owner Approval layer.
    return JsonResponse({
        "status": "accepted",
        "action": action,
        "auth_mode": auth_mode,
        "execution": "master_agent_owner_approval",
        "request": payload.get("request", {}),
    }, status=202)
