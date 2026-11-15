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
from django.views.decorators.csrf import csrf_protect

from .models import MojPropRequest
from .mojprop_catalog_contract import public_service_catalog
from .mojprop_receipts import make_receipt_token, verify_receipt_token, public_status_text

ROUTES = {choice[0] for choice in MojPropRequest.ROUTE_CHOICES}
HORIZONS = {choice[0] for choice in MojPropRequest.HORIZON_CHOICES}
MAX_REQUESTS_PER_WINDOW = 5
RATE_WINDOW = timedelta(minutes=10)


def _text(payload, key: str, limit: int) -> str:
    value = payload.get(key, "")
    return str(value).strip()[:limit] if value is not None else ""


MAX_BODY_BYTES = 16 * 1024
ALLOWED_FIELDS = frozenset((
    "name", "email", "service", "horizon", "notes", "consent", "website"
))


def _unique_pairs(pairs):
    """Reject ambiguous duplicate JSON fields, including email and consent."""
    values = {}
    for key, value in pairs:
        if key in values:
            raise ValueError("duplicate customer intake key")
        values[key] = value
    return values


def _payload(request):
    """Allow bounded JSON or a single-valued HTML form; reject hidden extras."""
    content_type = str(request.META.get("CONTENT_TYPE", "")).split(";", 1)[0].strip().lower()
    if content_type not in ("application/json", "application/x-www-form-urlencoded"):
        return None
    try:
        length = int(request.META.get("CONTENT_LENGTH") or 0)
    except (ValueError, TypeError):
        return None
    if length > MAX_BODY_BYTES or length < 0:
        return None
    if content_type == "application/json":
        body = request.body
        if len(body) > MAX_BODY_BYTES:
            return None
        try:
            value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_pairs)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return None
        if type(value) is not dict or set(value) - ALLOWED_FIELDS:
            return None
        return value
    form = request.POST
    if set(form.keys()) - ALLOWED_FIELDS:
        return None
    if any(len(form.getlist(key)) != 1 for key in form):
        return None
    return form


def _client_ip(request) -> str:
    """Use the peer address; forward headers are trusted only from allowed proxies."""
    from ipaddress import ip_address

    remote = str(request.META.get("REMOTE_ADDR") or "").strip()
    try:
        peer = str(ip_address(remote))
    except ValueError:
        return "unknown"

    # A public visitor must not choose a new rate-limit identity by sending
    # X-Real-IP. Only explicitly configured reverse proxy peers can assert it.
    allowed = getattr(settings, "MOJ_PROP_TRUSTED_PROXY_IPS", ())
    if not isinstance(allowed, (tuple, list, set, frozenset)):
        allowed = ()
    if peer in allowed:
        claimed = str(request.META.get("HTTP_X_REAL_IP") or "").strip()
        try:
            return str(ip_address(claimed))
        except ValueError:
            return peer
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
    # Tokens and buyer receipt state must never be kept in intermediary caches
    # or leaked in browser referrer data, including on error responses.
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@csrf_protect
@require_http_methods(["GET", "POST"])
def mojprop_intake(request):
    """Return a CSRF token or create one manual-review request."""
    if request.method == "GET":
        return _json({"ok": True, "csrf_token": get_token(request), "service": "moj-prop-intake",
                      "service_catalog": public_service_catalog()})

    payload = _payload(request)
    if payload is None:
        return _json({"ok": False, "detail": "Request body must be valid JSON."}, status=400)

    # Type-check JSON values; Python stringification must not turn arrays,
    # objects or integers into fabricated buyer names/addresses.
    for field in ("name", "email", "service", "horizon", "notes", "website"):
        if field in payload and not isinstance(payload[field], str):
            return _json({"ok": False, "detail": "Invalid field types."}, status=400)
    consent_value = payload.get("consent")
    if isinstance(payload, dict) and type(consent_value) is not bool:
        return _json({"ok": False, "detail": "Consent must be an explicit choice."}, status=400)

    # Honeypot field: real forms never display or populate this value.
    if _text(payload, "website", 120):
        return _json({"ok": False, "detail": "Request rejected."}, status=400)

    # Reject rather than silently truncate buyer identity or requested scope.
    # Truncation can convert two distinct contacts into the same CRM address,
    # or create a quote for a materially different scope than the buyer sent.
    limits = {"name": 200, "email": 254, "service": 30,
              "horizon": 20, "notes": 5000, "website": 120}
    oversized = {key: "Field exceeds maximum length."
                 for key, maximum in limits.items()
                 if len(payload.get(key, "")) > maximum}
    if oversized:
        return _json({"ok": False, "detail": "Request fields are too long.",
                      "fields": oversized}, status=400)

    name = _text(payload, "name", 200)
    email = _text(payload, "email", 254).lower()
    route = _text(payload, "service", 30)
    horizon = _text(payload, "horizon", 20)
    notes = _text(payload, "notes", 5000)
    consent = consent_value is True or (not isinstance(payload, dict) and str(consent_value).lower() in {"1", "true", "on"})

    errors = {}
    if len(name) < 2:
        errors["name"] = "Name is required."
    try:
        validate_email(email)
    except ValidationError:
        errors["email"] = "A valid email is required."
    else:
        # These domains cannot receive commercial proposals or retrieval links.
        domain = email.rsplit("@", 1)[-1].lower().rstrip(".")
        if domain in {"localhost", "example.invalid"} or domain.endswith(
            (".invalid", ".localhost", ".local", ".test")
        ):
            errors["email"] = "Use an email address capable of receiving a written offer."
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
            "receipt_token": make_receipt_token(request_obj.request_id),
            "status": request_obj.status,
            "next_step": "manual_review",
            "message": "Your request draft was received for manual review. No payment was taken.",
        },
        status=201,
    )


@require_http_methods(["GET"])
def mojprop_receipt_status(request):
    """Read only the public stage when holding the signed private receipt."""
    token = str(request.GET.get("receipt_token", ""))
    request_id = verify_receipt_token(token)
    if request_id is None:
        return _json(
            {"ok": False, "detail": "Receipt invalid or expired. Contact support using your original email."},
            status=404,
        )
    record = (MojPropRequest.objects.filter(request_id=request_id)
              .values_list("status", flat=True).first())
    if record is None:
        return _json({"ok": False, "detail": "Receipt unavailable."}, status=404)
    response = _json({
        "ok": True,
        "request_id": request_id,
        "status": record,
        "stage": public_status_text(record),
        "payment_status": "not_collected_by_this_service",
    })
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    return response
