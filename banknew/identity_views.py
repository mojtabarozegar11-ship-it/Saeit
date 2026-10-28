"""Same-origin Google session bridge; deliberately NOT routed or active yet.

Uses server-side Google token verification, persistent subject ownership,
atomic challenge consumption, Django CSRF/session middleware and no financial KYC.
"""
import hashlib
import json
import os
import time
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from banknew.google_identity import (
    generate_server_nonce, verify_google_credential, GoogleIdentityError,
)
from banknew.models import GoogleAccountLink, LoginChallenge

NONCE_SESSION_KEY = "mojpay_google_nonce"
LAST_START_KEY = "mojpay_google_last_start"
CLIENT_SUFFIX = ".apps.googleusercontent.com"


def _client(request):
    client = os.getenv("BANKNEW_GOOGLE_CLIENT_ID", "")
    if os.getenv("BANKNEW_AUTH_ENABLED") != "1" or not client.endswith(CLIENT_SUFFIX):
        return None
    if not request.is_secure() and not settings.DEBUG:
        return None
    return client


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _deny(message, code):
    return JsonResponse({"error": message}, status=code)


@never_cache
@require_GET
def start(request):
    client = _client(request)
    if not client:
        return _deny("Google account access is not configured.", 503)
    now = time.time()
    if now - request.session.get(LAST_START_KEY, 0) < 10:
        return _deny("Please wait before requesting another challenge.", 429)
    if not request.session.session_key:
        request.session.save()
    prior = request.session.pop(NONCE_SESSION_KEY, None)
    if prior:
        LoginChallenge.objects.filter(nonce_digest=_hash(prior),
                                      consumed_at__isnull=True).update(consumed_at=timezone.now())
    nonce = generate_server_nonce()
    LoginChallenge.objects.create(
        nonce_digest=_hash(nonce), session_digest=_hash(request.session.session_key),
        issued_at=timezone.now(),
    )
    request.session[NONCE_SESSION_KEY] = nonce
    request.session[LAST_START_KEY] = now
    return JsonResponse({
        "nonce": nonce, "client_id": client,
        "csrf_token": get_token(request), "expires_in": 300,
        "financial_kyc_verified": False, "payments_enabled": False,
    })


@never_cache
@csrf_protect
@require_POST
def finish(request):
    client = _client(request)
    if not client:
        return _deny("Google account access is not configured.", 503)
    nonce = request.session.pop(NONCE_SESSION_KEY, None)
    if not nonce or not request.session.session_key:
        return _deny("Login challenge missing or already used.", 400)
    if request.content_type != "application/json" or len(request.body) > 20000:
        return _deny("Invalid credential payload.", 400)
    try:
        data = json.loads(request.body)
        credential = data.get("credential") if isinstance(data, dict) else None
    except (ValueError, UnicodeError):
        credential = None
    now = timezone.now()
    consumed = LoginChallenge.objects.filter(
        nonce_digest=_hash(nonce), session_digest=_hash(request.session.session_key),
        consumed_at__isnull=True,
        issued_at__gte=now-timedelta(seconds=300),
        issued_at__lte=now,
    ).update(consumed_at=now)
    if consumed != 1:
        return _deny("Login challenge invalid or expired.", 400)
    try:
        principal = verify_google_credential(credential, client_id=client,
                                             expected_nonce=nonce)
    except GoogleIdentityError:
        return _deny("Google identity verification failed.", 401)
    try:
        with transaction.atomic():
            link = GoogleAccountLink.objects.select_related("user").filter(
                google_subject=principal.subject).first()
            if link is None:
                User = get_user_model()
                user = User(username="bn_"+uuid.uuid4().hex, email=principal.email)
                user.set_unusable_password()
                user.is_staff = False
                user.is_superuser = False
                user.save()
                link = GoogleAccountLink.objects.create(
                    user=user, google_subject=principal.subject,
                    verified_email=principal.email)
            else:
                user = link.user
                if link.verified_email != principal.email:
                    link.verified_email = principal.email
                    link.save(update_fields=["verified_email"])
            if not user.is_active or user.is_staff or user.is_superuser:
                return _deny("Account is not permitted.", 403)
    except (IntegrityError, Exception):
        return _deny("Identity binding is currently unavailable.", 503)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse({
        "authenticated": True, "financial_kyc_verified": False,
        "payments_enabled": False,
    })


@never_cache
@require_GET
def session_state(request):
    if not _client(request):
        return _deny("Google account access is not configured.", 503)
    if not request.user.is_authenticated:
        return _deny("Not authenticated.", 401)
    link = GoogleAccountLink.objects.filter(user=request.user).first()
    if link is None:
        return _deny("No verified Google account linked.", 403)
    return JsonResponse({
        "authenticated": True, "email": link.verified_email,
        "financial_kyc_verified": False, "payments_enabled": False,
    })


@never_cache
@csrf_protect
@require_POST
def signout(request):
    if not _client(request):
        return _deny("Google account access is not configured.", 503)
    logout(request)
    return JsonResponse({"authenticated": False})
