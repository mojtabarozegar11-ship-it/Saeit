"""Public, auditable Moj Prop request intake.

The endpoint records a request for manual review only. It never charges a user,
creates a payment intent, sends an email, or presents investment advice.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from uuid import UUID
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError, IntegrityError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from .models import MojPropRequest
from .mojprop_catalog_contract import public_service_catalog
from .mojprop_receipts import make_receipt_token, verify_receipt_token, public_status_text
from .mojprop_accessible_intake import request_form, created_receipt, status_form, status_result

ROUTES = {choice[0] for choice in MojPropRequest.ROUTE_CHOICES}
HORIZONS = {choice[0] for choice in MojPropRequest.HORIZON_CHOICES}
MAX_REQUESTS_PER_WINDOW = 5
RATE_WINDOW = timedelta(minutes=10)


def _text(payload, key: str, limit: int) -> str:
    value = payload.get(key, "")
    if type(value) is not str or len(value) > limit:
        raise ValueError("invalid value or length for " + key)
    value = value.strip()
    allowed_controls = "\n\t" if key == "notes" else ""
    if any((ord(ch) < 32 and ch not in allowed_controls)
           or ord(ch) == 127 or 0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise ValueError("unsafe control or surrogate in " + key)
    return value


MAX_BODY_BYTES = 16 * 1024
ALLOWED_FIELDS = frozenset((
    "name", "email", "service", "horizon", "notes", "consent", "website", "product_id",
    "idempotency_key",
))
# Only listed products may create an unpaid digital inquiry, never an invoice.
CATALOG_INQUIRY_PRODUCTS = frozenset((72, 225, 879))


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
    if content_type not in ("application/json", "application/x-www-form-urlencoded", "multipart/form-data"):
        return None
    try:
        length = int(request.META.get("CONTENT_LENGTH") or 0)
    except (ValueError, TypeError):
        return None
    if length < 0:
        return None
    if length > MAX_BODY_BYTES:
        raise OverflowError("customer request body too large")
    if content_type == "application/json":
        body = request.body
        if len(body) > MAX_BODY_BYTES:
            raise OverflowError("customer request body too large")
        try:
            value = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=_unique_pairs,
                parse_constant=lambda _name: (_ for _ in ()).throw(ValueError("invalid JSON number")),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
            return None
        if type(value) is not dict or set(value) - ALLOWED_FIELDS:
            return None
        return value
    form = request.POST
    # Never store uploaded documents or accept duplicate attacker-supplied keys.
    if request.FILES:
        return None
    # A normal browser form carries Django's CSRF hidden field. It is not
    # customer data and must not block an otherwise valid, consented lead.
    if set(form.keys()) - (ALLOWED_FIELDS | {"csrfmiddlewaretoken"}):
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
    configured = getattr(settings, "MOJPROP_TRUSTED_PROXIES", ())
    allowed = set(allowed) if isinstance(allowed, (tuple, list, set, frozenset)) else set()
    if isinstance(configured, (tuple, list, set, frozenset)):
        allowed.update(configured)
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


def _keyed_request_id(raw: str) -> str:
    """Map an unpredictable UUIDv4 to an existing DB-unique request_id.

    A keyed retry needs no new column/migration. The key never appears in an
    URL or server response, and a different payload with the same key fails.
    """
    if type(raw) is not str or len(raw) != 36:
        raise ValueError("Require canonical UUIDv4 idempotency key")
    try:
        key = UUID(raw)
    except (ValueError, AttributeError) as exc:
        raise ValueError("Require canonical UUIDv4 idempotency key") from exc
    if key.version != 4 or str(key) != raw:
        raise ValueError("Require canonical UUIDv4 idempotency key")
    tag = hmac.new(
        str(settings.SECRET_KEY).encode("utf-8"),
        ("mojprop:intake:v1:" + raw).encode("ascii"),
        hashlib.sha256,
    ).hexdigest().upper()[:24]
    return "MOJPROP-ID-" + tag


def _matches_keyed_retry(row, *, name, email, route, horizon, notes, product_id):
    """Keep a stolen/reused key from granting another buyer's private receipt."""
    return (
        row.source == "moj-prop-public" and row.consent is True
        and row.name == name and row.email == email
        and row.route == route and row.horizon == horizon
        and row.notes == notes and row.product_id == product_id
    )


def _intake_success(row, *, reused):
    return _json({
        "ok": True,
        "request_id": row.request_id,
        "receipt_token": make_receipt_token(row.request_id),
        "status": row.status,
        "next_step": "manual_review",
        "reused": reused,
        "message": (
            "Your prior request was found; no duplicate was created. No payment was taken."
            if reused else
            "Your request draft was received for manual review. No payment was taken."
        ),
    }, status=200 if reused else 201)


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


def _crm_storage_unavailable():
    """Fail closed without exposing buyer PII or claiming a lead was saved.

    A write might have committed before the connection failed. The browser's
    unchanged UUIDv4 idempotency key is the only safe retry/reconciliation key.
    """
    response = _json({
        "ok": False,
        "detail": "Request status unavailable. Keep your original request key and retry later.",
        "storage_confirmed": False,
        "payment_status": "not_collected_by_this_service",
    }, status=503)
    response["Retry-After"] = "60"
    return response


@csrf_protect
@require_http_methods(["GET", "POST"])
def mojprop_intake(request):
    """Maintain the original JSON API and expose a native HTML fallback."""
    modes = request.GET.getlist("format")
    if modes and modes != ["html"]:
        return _json({"ok": False, "detail": "Unsupported intake format."}, status=400)
    if modes == ["html"]:
        if request.method == "GET":
            return request_form(request)
        content_type = str(request.META.get("CONTENT_TYPE", "")).split(";", 1)[0].lower()
        if content_type != "application/x-www-form-urlencoded":
            return request_form(request, error="Use the standard request form.", status=400)
        api_response = _mojprop_intake_api(request)
        # The existing validated, idempotent CRM route remains authoritative.
        # Only server-generated response fields are presented in the HTML.
        try:
            result = json.loads(api_response.content.decode("utf-8"))
        except (UnicodeError, ValueError):
            return request_form(request, error="Request unavailable.", status=503)
        if result.get("ok") is True and api_response.status_code in (200, 201):
            return created_receipt(result, reused=result.get("reused") is True)
        detail = result.get("detail")
        detail = detail if type(detail) is str and len(detail) <= 200 else "Request unavailable."
        response = request_form(request, error=detail, status=api_response.status_code)
        if api_response.has_header("Retry-After"):
            response["Retry-After"] = api_response["Retry-After"]
        return response
    return _mojprop_intake_api(request)


def _mojprop_intake_api(request):
    """Original bounded validation, CRM persistence and signed receipts."""
    if request.method == "GET":
        return _json({"ok": True, "csrf_token": get_token(request), "service": "moj-prop-intake",
                      "service_catalog": public_service_catalog()})

    try:
        payload = _payload(request)
    except OverflowError:
        return _json({"ok": False, "detail": "Request exceeds safe intake size."}, status=413)
    if payload is None:
        return _json({"ok": False, "detail": "Use valid JSON or a single-valued HTML form."}, status=400)

    # Type-check JSON values; Python stringification must not turn arrays,
    # objects or integers into fabricated buyer names/addresses.
    for field in ("name", "email", "service", "horizon", "notes", "website", "idempotency_key"):
        if field in payload and not isinstance(payload[field], str):
            return _json({"ok": False, "detail": "Invalid field types."}, status=400)
    product_id = payload.get("product_id")
    content_type = str(request.META.get("CONTENT_TYPE", "")).split(";", 1)[0].lower()
    # Browser forms send scalar strings; JSON clients must send a real int.
    if (content_type in ("application/x-www-form-urlencoded", "multipart/form-data")
            and type(product_id) is str
            and product_id in {str(x) for x in CATALOG_INQUIRY_PRODUCTS}):
        product_id = int(product_id)
    consent_value = payload.get("consent")
    is_json_payload = type(payload) is dict
    # QueryDict subclasses dict, but ordinary form checkbox values are
    # strings ("on"/"1"), not JSON booleans. Keep the formats distinct.
    if is_json_payload and type(consent_value) is not bool:
        return _json({"ok": False, "detail": "Consent must be an explicit choice."}, status=400)

    # Reject rather than silently truncate buyer identity or requested scope.
    # Truncation can convert two distinct contacts into the same CRM address,
    # or create a quote for a materially different scope than the buyer sent.
    limits = {"name": 200, "email": 254, "service": 30,
              "horizon": 20, "notes": 5000, "website": 120,
              "idempotency_key": 36}
    oversized = {key: "Field exceeds maximum length."
                 for key, maximum in limits.items()
                 if len(payload.get(key, "")) > maximum}
    if oversized:
        return _json({"ok": False, "detail": "Request fields are too long.",
                      "fields": oversized}, status=400)

    # Honeypot field: real forms never display or populate this value.
    try:
        honeypot = _text(payload, "website", 120)
    except ValueError:
        return _json({"ok": False, "detail": "Malformed request fields."}, status=400)
    if honeypot:
        return _json({"ok": False, "detail": "Request rejected."}, status=400)

    try:
        name = _text(payload, "name", 200)
        email = _text(payload, "email", 254).lower()
        route = _text(payload, "service", 30)
        horizon = _text(payload, "horizon", 20)
        notes = _text(payload, "notes", 5000)
    except ValueError:
        return _json({"ok": False, "detail": "Malformed customer fields."}, status=400)
    consent = consent_value is True or (
        not is_json_payload and isinstance(consent_value, str)
        and consent_value.lower() in {"1", "true", "on"}
    )

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
    if route == "digital":
        if type(product_id) is not int or product_id not in CATALOG_INQUIRY_PRODUCTS:
            errors["product_id"] = "Choose one available digital product."
    elif product_id not in (None, ""):
        errors["product_id"] = "Product ID is permitted only for digital inquiries."
    if horizon not in HORIZONS:
        errors["horizon"] = "Choose a valid time horizon."
    if len(notes) < 20:
        errors["notes"] = "Please describe the objective in at least 20 characters."
    if not consent:
        errors["consent"] = "Consent is required for a manual-review request."
    if errors:
        return _json({"ok": False, "detail": "Please correct the highlighted fields.", "fields": errors}, status=400)

    product_scope = product_id if route == "digital" else None
    keyed_id = None
    if "idempotency_key" in payload:
        try:
            keyed_id = _keyed_request_id(payload["idempotency_key"])
        except ValueError:
            return _json({"ok": False, "detail": "Invalid idempotency key."}, status=400)

    def existing_keyed_response(row):
        if not _matches_keyed_retry(
            row, name=name, email=email, route=route,
            horizon=horizon, notes=notes, product_id=product_scope,
        ):
            # Never disclose the record, account or receipt on key reuse.
            return _json({"ok": False, "detail": "Request key conflict."}, status=409)
        return _intake_success(row, reused=True)

    # Reconnect before throttling: an already persisted, identical retry must
    # recover the receipt instead of creating a sixth lead or a second quote.
    if keyed_id:
        try:
            prior = MojPropRequest.objects.filter(request_id=keyed_id).first()
        except DatabaseError:
            return _crm_storage_unavailable()
        if prior is not None:
            return existing_keyed_response(prior)

    ip_hash = _ip_hash(request)
    try:
        blocked = _rate_limited(email, ip_hash)
    except DatabaseError:
        return _crm_storage_unavailable()
    if blocked:
        response = _json(
            {"ok": False, "detail": "Too many requests. Please try again later.", "retry_after": 600},
            status=429,
        )
        response["Retry-After"] = "600"
        return response

    request_obj = None
    for _ in range(1 if keyed_id else 3):
        request_id = keyed_id or _request_id()
        try:
            with transaction.atomic():
                request_obj = MojPropRequest.objects.create(
                    request_id=request_id,
                    name=name,
                    email=email,
                    route=route,
                    horizon=horizon,
                    notes=notes,
                    product_id=product_scope,
                    consent=True,
                    source="moj-prop-public",
                    ip_hash=ip_hash,
                    user_agent=str(request.META.get("HTTP_USER_AGENT", ""))[:300],
                )
            break
        except IntegrityError:
            if keyed_id:
                # Unique DB index serializes competing first POSTs. Never
                # generate a second CRM lead for a conflicting keyed retry.
                prior = MojPropRequest.objects.filter(request_id=keyed_id).first()
                if prior is not None:
                    return existing_keyed_response(prior)
                return _json({"ok": False, "detail": "Request state unavailable."}, status=503)
    if request_obj is None:
        return _json({"ok": False, "detail": "Could not allocate a request ID. Please retry."}, status=503)

    return _intake_success(request_obj, reused=False)

@csrf_protect
@require_http_methods(["GET", "POST"])
def mojprop_receipt_status(request):
    """Read only the public stage when holding the signed private receipt."""
    formats = request.GET.getlist("format")
    if formats and formats != ["html"]:
        return _json({"ok": False, "detail": "Unsupported status format."}, status=400)
    if formats == ["html"]:
        # Status secrets are accepted only in a CSRF-protected POST body. Do
        # not copy bearer tokens into URL/query, HTML cache or external links.
        if request.method == "GET":
            if request.GET.getlist("receipt_token"):
                return status_form(request, error="Use the private POST status form.", status=400)
            return status_form(request)
        kind = str(request.META.get("CONTENT_TYPE", "")).split(";", 1)[0].lower()
        if kind != "application/x-www-form-urlencoded":
            return status_form(request, error="Use the private status form.", status=400)
        form = request.POST
        if (set(form.keys()) - {"csrfmiddlewaretoken", "receipt_token"}
                or any(len(form.getlist(key)) != 1 for key in form)
                or len(form.getlist("receipt_token")) != 1):
            return status_form(request, error="Invalid receipt submission.", status=400)
        token = form.get("receipt_token", "")
        if type(token) is not str or not 1 <= len(token) <= 256:
            return status_form(request, error="Receipt invalid or expired.", status=404)
        request_id = verify_receipt_token(token)
        if request_id is None:
            return status_form(request, error="Receipt invalid or expired.", status=404)
        stage = (MojPropRequest.objects.filter(request_id=request_id)
                 .values_list("status", flat=True).first())
        if stage is None:
            return status_form(request, error="Receipt unavailable.", status=404)
        return status_result(request_id, public_status_text(stage))
    # A bearer receipt must be unambiguous: reject duplicate query parameters.
    # QueryDict.get() silently selects the last value otherwise.
    if request.method == "POST":
        if str(request.META.get("CONTENT_TYPE", "")).split(";", 1)[0].lower() != "application/json":
            return _json({"ok": False, "detail": "JSON receipt proof required."}, status=400)
        try:
            if len(request.body) > 1024:
                return _json({"ok": False, "detail": "Receipt proof is too long."}, status=413)
            body = json.loads(request.body.decode("utf-8"), object_pairs_hook=_unique_pairs)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
            return _json({"ok": False, "detail": "Invalid receipt proof."}, status=400)
        token = body.get("receipt_token") if type(body) is dict and set(body) == {"receipt_token"} else ""
    else:
        # Support old signed tokens in read-only GET for previously issued receipts.
        tokens = request.GET.getlist("receipt_token")
        token = tokens[0] if len(tokens) == 1 else ""
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
