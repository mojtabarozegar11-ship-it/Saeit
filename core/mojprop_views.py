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


def _text(payload, key: str, limit: int) -> str:
    value = payload.get(key, "")
    return str(value).strip()[:limit] if value is not None else ""


def _payload(request):
    content_type = request.META.get("CONTENT_TYPE", "")
    if content_type.startswith("application/json"):
        try:
            value = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None
    return request.POST


def _client_ip(request) -> str:
    # Proxy-provided values are bounded and hashed immediately; the raw value is never stored.
    return str(
        request.META.get("HTTP_X_REAL_IP")
        or request.META.get("REMOTE_ADDR")
        or "unknown"
    ).strip()[:128]


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

    payload = _payload(request)
    if payload is None:
        return _json({"ok": False, "detail": "Request body must be valid JSON."}, status=400)

    # Honeypot field: real forms never display or populate this value.
    if _text(payload, "website", 120):
        return _json({"ok": False, "detail": "Request rejected."}, status=400)

    name = _text(payload, "name", 200)
    email = _text(payload, "email", 254).lower()
    route = _text(payload, "service", 30)
    horizon = _text(payload, "horizon", 20)
    notes = _text(payload, "notes", 5000)
    consent_value = payload.get("consent")
    consent = consent_value is True or str(consent_value).lower() in {"1", "true", "on", "yes"}

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
        return _json(
            {"ok": False, "detail": "Too many requests. Please try again later.", "retry_after": 600},
            status=429,
        )

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
