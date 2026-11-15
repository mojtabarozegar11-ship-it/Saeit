"""Public, auditable Moj Prop request intake.

The endpoint records a request for manual review only. It never charges a user,
creates a payment intent, sends an email, or presents investment advice.
"""
from __future__ import annotations

import hashlib
import ipaddress
import hmac
import json
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, DatabaseError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import MojPropRequest, MojPropRateBucket

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


class MojPropQuotaExceeded(Exception):
    """Atomic quota reject: no lead persisted and no charge collected."""


class MojPropUntrustedOrigin(Exception):
    """No trusted client address could be determined."""


def _client_ip(request) -> str:
    # X-Real-IP and X-Forwarded-For are client controlled unless the
    # operator has pinned a trusted reverse proxy. Do not trust by default.
    raw = request.META.get("REMOTE_ADDR")
    try:
        if type(raw) is not str:
            raise ValueError("no network origin")
        return ipaddress.ip_address(raw.strip()).compressed
    except ValueError as exc:
        raise MojPropUntrustedOrigin("client_origin_unavailable") from exc


def _ip_hash(request) -> str:
    secret = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(secret, _client_ip(request).encode("ascii"), hashlib.sha256).hexdigest()


def _request_id() -> str:
    return f"MOJPROP-{timezone.now():%Y%m%d}-{secrets.token_hex(4).upper()}"


def _consume_quota(email: str, ip_hash: str, now) -> None:
    """Called INSIDE the transaction creating the canonical lead.

    All cPanel workers share one DB row and row lock for each HMAC scope.
    A rejected request rolls back *both* counters and the lead row.
    """
    if not now.tzinfo:
        raise ValueError("timezone aware clock required")
    minute = (now.minute // 10) * 10
    floor = now.replace(minute=minute, second=0, microsecond=0)
    expires = floor + timedelta(minutes=30)
    for scope, value in (("origin", ip_hash), ("email", email)):
        material = f"mojprop:v1:{scope}:{floor.isoformat()}:{value}"
        digest = hmac.new(settings.SECRET_KEY.encode("utf-8"),
                          material.encode("utf-8"), hashlib.sha256).hexdigest()
        bucket, _ = MojPropRateBucket.objects.select_for_update().get_or_create(
            digest=digest,
            defaults={"count": 0, "expires_at": expires},
        )
        if bucket.count >= MAX_REQUESTS_PER_WINDOW:
            raise MojPropQuotaExceeded
        bucket.count += 1
        bucket.save(update_fields=["count"])


def _json(data, status=200):
    response = JsonResponse(data, status=status)
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["GET", "POST"])
@csrf_protect
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

    try:
        ip_hash = _ip_hash(request)
    except MojPropUntrustedOrigin:
        return _json({"ok": False, "detail": "Request origin cannot be verified."},
                     status=503)
    request_obj = None
    for _ in range(3):
        try:
            with transaction.atomic():
                _consume_quota(email, ip_hash, timezone.now())
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
        except MojPropQuotaExceeded:
            return _json(
                {"ok": False, "detail": "Too many requests. Please try again later.",
                 "retry_after": 600}, status=429)
        except IntegrityError:
            # Both quota increments have rolled back; retry only a genuine
            # request-id collision. Persistent errors fail closed below.
            continue
        except DatabaseError:
            return _json({"ok": False, "detail": "Request service unavailable."},
                         status=503)
    if request_obj is None:
        return _json({"ok": False, "detail": "Request storage temporarily unavailable."},
                     status=503)

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
