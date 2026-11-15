"""Public, auditable Moj Prop request intake.

The endpoint records a request for manual review only. It never charges a user,
creates a payment intent, sends an email, or presents investment advice.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import MojPropRequest

ROUTES = {choice[0] for choice in MojPropRequest.ROUTE_CHOICES}
HORIZONS = {choice[0] for choice in MojPropRequest.HORIZON_CHOICES}
MAX_REQUESTS_PER_WINDOW = 5
RATE_WINDOW = timedelta(minutes=10)
MAX_REQUEST_BYTES = 16_384
FIELD_LIMITS = {
    "name": 200, "email": 254, "service": 30, "horizon": 20,
    "notes": 5000, "website": 120,
}
ALLOWED_FIELDS = frozenset((*FIELD_LIMITS, "consent"))


def _text(payload, key: str, limit: int) -> str:
    """Never silently truncate buyer input or coerce structured data to a string."""
    value = payload.get(key, "")
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("invalid field: " + key)
    value = value.strip()
    allowed_controls = chr(10) + chr(9) if key == "notes" else ""
    if any(ord(char) < 32 and char not in allowed_controls for char in value):
        raise ValueError("control character in " + key)
    return value


def _unique_json_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def _payload(request):
    if len(request.body) > MAX_REQUEST_BYTES:
        raise OverflowError("request body exceeds intake limit")
    content_type = request.META.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower()
    if content_type == "application/json":
        try:
            value = json.loads(
                request.body.decode("utf-8"),
                object_pairs_hook=_unique_json_pairs,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid JSON number")),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return None
        return value if isinstance(value, dict) else None
    if content_type == "application/x-www-form-urlencoded":
        return request.POST
    return None


def _client_ip(request) -> str:
    # Proxy-provided values are bounded and hashed immediately; the raw value is never stored.
    peer = str(request.META.get("REMOTE_ADDR") or "unknown").strip()[:128]
    # Never trust a spoofable client-supplied proxy header by default.
    trusted_proxies = getattr(settings, "MOJPROP_TRUSTED_PROXIES", ())
    if isinstance(trusted_proxies, (list, tuple, frozenset)) and peer in trusted_proxies:
        return str(request.META.get("HTTP_X_REAL_IP") or peer).strip()[:128]
    return peer


def _ip_hash(request) -> str:
    secret = str(getattr(settings, "SECRET_KEY", "change-me")).encode("utf-8")
    return hmac.new(secret, _client_ip(request).encode("utf-8"), hashlib.sha256).hexdigest()


def _request_id() -> str:
    return f"MOJPROP-{timezone.now():%Y%m%d}-{secrets.token_hex(4).upper()}"


def _rate_limited(email: str, ip_hash: str) -> bool:
    since = timezone.now() - RATE_WINDOW
    recent = MojPropRequest.objects.filter(created_at__gte=since)
    return (
        recent.filter(ip_hash=ip_hash).count() >= MAX_REQUESTS_PER_WINDOW
        or recent.filter(email__iexact=email).count() >= MAX_REQUESTS_PER_WINDOW
    )


def _json(data, status=200):
    response = JsonResponse(data, status=status)
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["GET", "POST"])
def mojprop_intake(request):
    """Return a CSRF token or create one manual-review request."""
    if request.method == "GET":
        return _json({"ok": True, "csrf_token": get_token(request), "service": "moj-prop-intake"})

    try:
        payload = _payload(request)
    except OverflowError:
        return _json({"ok": False, "detail": "Request is too large."}, status=413)
    if payload is None:
        return _json({"ok": False, "detail": "Use valid JSON or form data."}, status=400)
    if set(payload) - ALLOWED_FIELDS:
        return _json({"ok": False, "detail": "Unknown request fields."}, status=400)
    try:
        fields = {name: _text(payload, name, limit) for name, limit in FIELD_LIMITS.items()}
    except ValueError:
        return _json({"ok": False, "detail": "A field is malformed or too long."}, status=400)

    # Honeypot field: real forms never display or populate this value.
    if fields["website"]:
        return _json({"ok": False, "detail": "Request rejected."}, status=400)

    name = fields["name"]
    email = fields["email"].lower()
    route = fields["service"]
    horizon = fields["horizon"]
    notes = fields["notes"]
    consent_value = payload.get("consent")
    consent = consent_value is True or (
        request.content_type.split(";", 1)[0].lower() == "application/x-www-form-urlencoded"
        and consent_value in ("1", "true", "on", "yes")
    )

    errors = {}
    if len(name) < 2:
        errors["name"] = "Name is required."
    try:
        validate_email(email)
    except ValidationError:
        errors["email"] = "A valid email is required."
    if route not in ROUTES:
        errors["service"] = "Choose a valid service route."
    if horizon not in HORIZONS:
        errors["horizon"] = "Choose a valid time horizon."
    if len(notes) < 20:
        errors["notes"] = "Please describe the objective in at least 20 characters."
    if not consent:
        errors["consent"] = "Consent is required for a manual-review request."
    if errors:
        return _json({"ok": False, "detail": "Please correct the highlighted fields.", "fields": errors}, status=400)

    ip_hash = _ip_hash(request)
    if _rate_limited(email, ip_hash):
        response = _json(
            {"ok": False, "detail": "Too many requests. Please try again later.", "retry_after": 600},
            status=429,
        )
        response["Retry-After"] = "600"
        return response

    request_obj = None
    for _ in range(3):
        try:
            with transaction.atomic():
                request_obj = MojPropRequest.objects.create(
                    request_id=_request_id(),
                    name=name,
                    email=email,
                    route=route,
                    horizon=horizon,
                    notes=notes,
                    consent=True,
                    source="moj-prop-public",
                    ip_hash=ip_hash,
                    user_agent=str(request.META.get("HTTP_USER_AGENT", ""))[:300],
                )
            break
        except IntegrityError:
            continue
    if request_obj is None:
        return _json({"ok": False, "detail": "Could not allocate a request ID. Please retry."}, status=503)

    return _json(
        {
            "ok": True,
            "request_id": request_obj.request_id,
            "status": request_obj.status,
            "next_step": "manual_review",
            "message": "Your request draft was received for manual review. No payment was taken.",
        },
        status=201,
    )
