"""Scoped login/session endpoints using the existing MojPlayWin Django users."""
import json
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from .models import LoginAttemptBucket

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST


@require_GET
@ensure_csrf_cookie
def csrf_view(request):
    """Bootstrap CSRF for the current static game without replacing its HTML."""
    response = JsonResponse({"csrf_token": get_token(request)})
    response["Cache-Control"] = "private, no-store"
    return response


def _authenticate_with_throttle(request, username, password):
    """Serialize attempts per (client network address, normalized username).

    Uses the existing site DB so worker restarts/multiple Passenger processes
    cannot reset attempts. Only a keyed digest is persisted, never credentials
    or a plaintext IP address. Never trust caller-supplied forwarded-IP headers.
    """
    source_ip = str(request.META.get("REMOTE_ADDR") or "unknown")
    digest = salted_hmac(
        "living_cities.login_limit.v1",
        source_ip + "\x00" + username.strip().casefold(),
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()
    now = timezone.now()
    window = timedelta(minutes=15)
    with transaction.atomic():
        bucket, _created = LoginAttemptBucket.objects.get_or_create(
            key_digest=digest, defaults={"first_failure_at": now}
        )
        bucket = LoginAttemptBucket.objects.select_for_update().get(pk=bucket.pk)
        if bucket.blocked_until and bucket.blocked_until > now:
            return None, True
        if now - bucket.first_failure_at >= window:
            bucket.failures = 0
            bucket.first_failure_at = now
            bucket.blocked_until = None
        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_active:
            bucket.failures += 1
            if bucket.failures >= 5:
                bucket.blocked_until = now + window
            bucket.save(update_fields=["failures", "first_failure_at", "blocked_until"])
            return None, bucket.blocked_until is not None
        bucket.failures = 0
        bucket.first_failure_at = now
        bucket.blocked_until = None
        bucket.save(update_fields=["failures", "first_failure_at", "blocked_until"])
        return user, False


@require_POST
@csrf_protect
def login_view(request):
    if len(request.body) > 4096:
        return JsonResponse({"error": "invalid_request"}, status=400)
    try:
        credentials = json.loads(request.body or "{}")
    except (TypeError, ValueError, UnicodeDecodeError):
        credentials = None
    if not isinstance(credentials, dict):
        return JsonResponse({"error": "invalid_request"}, status=400)
    username = credentials.get("username")
    password = credentials.get("password")
    if (not isinstance(username, str) or not isinstance(password, str)
            or not username or len(username) > 150
            or not password or len(password) > 1024):
        return JsonResponse({"error": "invalid_credentials"}, status=401)
    try:
        user, blocked = _authenticate_with_throttle(request, username, password)
    except DatabaseError:
        # The shared limit must never silently downgrade to an unlimited login.
        return JsonResponse({"error": "authentication_temporarily_unavailable"}, status=503)
    if blocked:
        response = JsonResponse({"error": "too_many_login_attempts"}, status=429)
        response["Retry-After"] = "900"
        response["Cache-Control"] = "private, no-store"
        return response
    if user is None:
        response = JsonResponse({"error": "invalid_credentials"}, status=401)
        response["Cache-Control"] = "private, no-store"
        return response
    login(request, user)
    # login() rotates the CSRF secret; return the *new* masked token so the
    # browser can immediately issue a protected business action.
    response = JsonResponse({
        "authenticated": True,
        "user": {"id": user.pk, "username": user.get_username()},
        "csrf_token": get_token(request),
    })
    response["Cache-Control"] = "private, no-store"
    return response


@require_GET
def me_view(request):
    if not request.user.is_authenticated:
        response = JsonResponse({"authenticated": False}, status=401)
    else:
        response = JsonResponse({
            "authenticated": True,
            "user": {"id": request.user.pk, "username": request.user.get_username()},
        })
    response["Cache-Control"] = "private, no-store"
    return response


@require_POST
@csrf_protect
def logout_view(request):
    logout(request)
    response = JsonResponse({"authenticated": False})
    response["Cache-Control"] = "private, no-store"
    return response
