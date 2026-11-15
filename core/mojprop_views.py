"""Public, auditable Moj Prop request intake.

The endpoint records a request for manual review only. It never charges a user,
creates a payment intent, sends an email, or presents investment advice.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
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
MAX_BODY_BYTES = 16 * 1024
PUBLIC_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))
FORM_FIELDS = frozenset(("name", "email", "service", "horizon", "notes", "consent", "website"))
RESERVED_EMAIL_DOMAINS = frozenset(("example.com", "example.org", "example.net", "guest.mojplaywin.com"))


def _text(payload, key: str, limit: int) -> str | None:
    """Refuse oversized and non-string claims; never silently trim evidence."""
    value = payload.get(key, "")
    if (type(value) is not str or len(value) > limit
            or any(ord(char) < 32 and char not in "\n\t" for char in value)):
        return None
    return value.strip()


def _object_pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_field")
        result[key] = value
    return result


def _payload(request):
    content_type = request.META.get("CONTENT_TYPE", "")
    if content_type.startswith("application/json"):
        try:
            body = request.body
            if len(body) > MAX_BODY_BYTES:
                return None
            value = json.loads(body.decode("utf-8"),
                               object_pairs_hook=_object_pairs_no_duplicates)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return None
        return value if type(value) is dict else None
    if content_type.startswith("application/x-www-form-urlencoded"):
        if any(len(request.POST.getlist(key)) != 1 for key in request.POST):
            return None
        return request.POST
    return None


def _client_ip(request) -> str:
    """Never trust client-spoofed X-Real-IP without an explicitly trusted proxy."""
    raw = request.META.get("REMOTE_ADDR", "")
    if type(raw) is not str or len(raw) > 64:
        raise ValueError("missing_or_invalid_remote_ip")
    address = str(ipaddress.ip_address(raw))
    trusted = getattr(settings, "MOJ_PROP_TRUSTED_PROXY_IPS", ())
    if (type(trusted) in (tuple, list, frozenset) and address in trusted):
        forwarded = request.META.get("HTTP_X_REAL_IP", "")
        if type(forwarded) is str and forwarded:
            address = str(ipaddress.ip_address(forwarded))
    return address


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
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Referrer-Policy"] = "same-origin"
    response["X-Content-Type-Options"] = "nosniff"
    if status == 429:
        response["Retry-After"] = "600"
    return response


@require_http_methods(["GET", "POST"])
def mojprop_intake(request):
    """Return a CSRF token or create one manual-review request."""
    # This public service belongs only to MojPlayWin, not third-party mirrors.
    if (not request.is_secure()
            or request.get_host().split(":")[0].lower() not in PUBLIC_HOSTS):
        return _json({"ok": False, "detail": "Not available."}, status=404)
    if request.method == "GET":
        return _json({"ok": True, "csrf_token": get_token(request), "service": "moj-prop-intake"})
    try:
        content_length = int(request.META.get("CONTENT_LENGTH", "0"))
    except (ValueError, TypeError):
        return _json({"ok": False, "detail": "Invalid content length."}, status=400)
    if content_length > MAX_BODY_BYTES:
        return _json({"ok": False, "detail": "Request too large."}, status=413)

    payload = _payload(request)
    if payload is None or set(payload) - FORM_FIELDS:
        return _json({"ok": False, "detail": "Invalid or unexpected request fields."}, status=400)

    # The honeypot must be an ordinary empty string; malformed values fail closed.
    website = _text(payload, "website", 120)
    if website is None or website:
        return _json({"ok": False, "detail": "Request rejected."}, status=400)

    name = _text(payload, "name", 200)
    submitted_email = _text(payload, "email", 254)
    email = submitted_email.lower() if submitted_email is not None else ""
    route = _text(payload, "service", 30)
    horizon = _text(payload, "horizon", 20)
    notes = _text(payload, "notes", 5000)
    consent_value = payload.get("consent")
    consent = consent_value is True or str(consent_value).lower() in {"1", "true", "on", "yes"}

    errors = {}
    if name is None or len(name) < 2:
        errors["name"] = "Name is required."
    try:
        validate_email(email)
        domain = email.rsplit("@", 1)[1]
        if (domain in RESERVED_EMAIL_DOMAINS
                or domain.endswith((".invalid", ".local", ".test", ".example"))):
            raise ValidationError("Reserved contact email")
    except ValidationError:
        errors["email"] = "A valid customer email is required."
    if route not in ROUTES:
        errors["service"] = "Choose a valid service route."
    if horizon not in HORIZONS:
        errors["horizon"] = "Choose a valid time horizon."
    if notes is None or len(notes) < 20:
        errors["notes"] = "Please describe the objective in 20 to 5000 characters."
    if not consent:
        errors["consent"] = "Consent is required for a manual-review request."
    if errors:
        return _json({"ok": False, "detail": "Please correct the highlighted fields.", "fields": errors}, status=400)

    try:
        ip_hash = _ip_hash(request)
    except ValueError:
        return _json({"ok": False, "detail": "Request unavailable."}, status=503)
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
