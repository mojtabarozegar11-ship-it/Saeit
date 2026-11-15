"""Free educational research updates: verified opt-in and revocable consent.

This module never publishes financial recommendations, sends marketing content,
executes trades, grants paid entitlements, or fabricates customer registrations.
Confirmation mail is the sole outbound message and fails closed unless a real
SMTP sender and an explicit deployment-level approval switch are present.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from datetime import timedelta
from html import escape

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .signal_free_models import MojSignalFreeSubscription


log = logging.getLogger(__name__)
_TOKEN_SALT = "mojtaba-free-educational-signals-v1"
_CONFIRM_TTL = 48 * 60 * 60
_UNSUB_TTL = 5 * 365 * 24 * 60 * 60
_RESEND_COOLDOWN = timedelta(minutes=15)
_HOURLY_IP_LIMIT = 5
_PUBLIC_BASE = "https://mojplaywin.com"


def _answer(payload, status=200):
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "no-store, private"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _smtp_ready():
    """Never email until specifically enabled with a real authenticated SMTP."""
    if getattr(settings, "MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED", False) is not True:
        return False
    if getattr(settings, "EMAIL_BACKEND", "") != "django.core.mail.backends.smtp.EmailBackend":
        return False
    required = (
        getattr(settings, "EMAIL_HOST", ""),
        getattr(settings, "EMAIL_HOST_USER", ""),
        getattr(settings, "EMAIL_HOST_PASSWORD", ""),
        getattr(settings, "DEFAULT_FROM_EMAIL", ""),
    )
    if not all(type(value) is str and value.strip() for value in required):
        return False
    if (getattr(settings, "EMAIL_USE_TLS", False) is True) == (getattr(settings, "EMAIL_USE_SSL", False) is True):
        return False
    try:
        validate_email(getattr(settings, "DEFAULT_FROM_EMAIL"))
    except ValidationError:
        return False
    return type(getattr(settings, "EMAIL_PORT", None)) is int and 1 <= settings.EMAIL_PORT <= 65535


def _sign(subscriber, purpose):
    if purpose not in ("confirm", "unsubscribe"):
        raise ValueError("unknown token purpose")
    return signing.dumps(
        {"id": subscriber.pk, "nonce": subscriber.nonce, "purpose": purpose},
        salt=_TOKEN_SALT,
        compress=False,
    )


def _validated_token(token, purpose):
    if type(token) is not str or len(token) > 512:
        return None
    try:
        payload = signing.loads(
            token, salt=_TOKEN_SALT,
            max_age=_CONFIRM_TTL if purpose == "confirm" else _UNSUB_TTL,
        )
    except (signing.BadSignature, signing.SignatureExpired, TypeError, ValueError):
        return None
    if (type(payload) is not dict
            or type(payload.get("id")) is not int
            or type(payload.get("nonce")) is not str
            or payload.get("purpose") != purpose):
        return None
    try:
        subscriber = MojSignalFreeSubscription.objects.get(pk=payload["id"])
    except MojSignalFreeSubscription.DoesNotExist:
        return None
    return subscriber if constant_time_compare(subscriber.nonce, payload["nonce"]) else None


def free_unsubscribe_link(subscriber):
    """Used only in separately approved educational emails to active members."""
    if subscriber.status != "confirmed":
        raise ValueError("only confirmed members receive update links")
    return _PUBLIC_BASE + reverse("moj_signal_free_unsubscribe", args=[_sign(subscriber, "unsubscribe")])


def _ip_hash(request):
    # The client cannot influence this key with X-Forwarded-For/X-Real-IP.
    remote = str(request.META.get("REMOTE_ADDR") or "unknown")
    key = str(settings.SECRET_KEY).encode("utf-8")
    return hmac.new(key, remote.encode("utf-8"), hashlib.sha256).hexdigest()


def _valid_json(request):
    if request.content_type != "application/json":
        return None
    if len(request.body) > 2048:
        return None
    try:
        def unique(pairs):
            obj = {}
            for name, value in pairs:
                if name in obj:
                    raise ValueError("duplicate JSON key")
                obj[name] = value
            return obj
        data = json.loads(request.body.decode("utf-8"), object_pairs_hook=unique)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, RecursionError):
        return None
    if type(data) is not dict or set(data) != {"email", "consent", "website"}:
        return None
    if type(data["email"]) is not str or type(data["consent"]) is not bool or type(data["website"]) is not str:
        return None
    if data["website"] or data["consent"] is not True:
        return None
    email = data["email"].strip().lower()
    if len(email) > 254 or any(ord(ch) < 32 or ord(ch) == 127 for ch in email):
        return None
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


@csrf_protect
@require_http_methods(["GET", "POST"])
def signal_free_subscribe(request):
    """GET gives CSRF availability; POST requests a verification email only."""
    if request.method == "GET":
        return _answer({
            "ok": True,
            "enabled": _smtp_ready(),
            "csrf_token": get_token(request),
            "product": "free-historical-research-updates",
            "agent": "mojtaba.bot.ai",
            "paid_entitlement": False,
        })
    if not _smtp_ready():
        return _answer({"ok": False, "detail": "Verified free email registration is not currently available."}, 503)
    email = _valid_json(request)
    if not email:
        return _answer({"ok": False, "detail": "Valid email and independent consent are required."}, 400)
    now = timezone.now()
    ip_key = _ip_hash(request)
    if MojSignalFreeSubscription.objects.filter(
        ip_hash=ip_key, confirmation_sent_at__gte=now - timedelta(hours=1)
    ).count() >= _HOURLY_IP_LIMIT:
        return _answer({"ok": False, "detail": "Too many registration requests. Please try later."}, 429)
    # Uniform success body prevents active/unsubscribed account enumeration.
    accepted = {"ok": True, "status": "verification_if_eligible",
                "detail": "If eligible, a confirmation link is sent. Check your inbox."}
    try:
        with transaction.atomic():
            subscriber = (
                MojSignalFreeSubscription.objects.select_for_update()
                .filter(email=email).first()
            )
            if subscriber and subscriber.status == "confirmed":
                return _answer(accepted, 202)
            if subscriber and subscriber.confirmation_sent_at and (
                subscriber.confirmation_sent_at > now - _RESEND_COOLDOWN
            ):
                return _answer(accepted, 202)
            if subscriber is None:
                subscriber = MojSignalFreeSubscription(email=email)
            subscriber.status = "pending"
            subscriber.nonce = secrets.token_urlsafe(24)
            subscriber.consent_at = now
            subscriber.consent_version = "edu-free-v1"
            subscriber.confirmed_at = None
            subscriber.unsubscribed_at = None
            subscriber.source = "signal-desk"
            subscriber.ip_hash = ip_key
            subscriber.confirmation_sent_at = now
            subscriber.save()
            url = _PUBLIC_BASE + reverse("moj_signal_free_confirm", args=[_sign(subscriber, "confirm")])
            sent = send_mail(
                "Confirm free educational research updates — Mojtaba.bot.ai",
                "You requested occasional free historical market-research education.\n"
                "Confirm your separate opt-in within 48 hours:\n" + url + "\n\n"
                "This is not a trading signal, paid service, or promise of profits.\n"
                "If you did not request this, ignore this email.\n"
                "No marketing will be sent until you explicitly confirm.\n",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            if sent != 1:
                raise RuntimeError("SMTP did not confirm one accepted message")
    except (Exception,) as exc:
        # Do not log recipients, credentials or provider exception text.
        log.warning("mojtaba_free_subscription_confirmation_unavailable")
        return _answer({"ok": False, "detail": "Secure confirmation is unavailable. No registration was confirmed."}, 503)
    return _answer(accepted, 202)


def _confirmation_page(request, title, message, action_label):
    action = escape(request.path, quote=True)
    csrf = escape(get_token(request), quote=True)
    return HttpResponse(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="referrer" content="no-referrer">'
        '<title>' + escape(title) + '</title></head><body>'
        '<main style="max-width:620px;margin:6rem auto;font:17px system-ui;padding:2rem">'
        '<h1>' + escape(title) + '</h1><p>' + escape(message) + '</p>'
        '<form method="post" action="' + action + '">'
        '<input type="hidden" name="csrfmiddlewaretoken" value="' + csrf + '">'
        '<button type="submit">' + escape(action_label) + '</button></form>'
        '<p>No payments, automatic trading or guaranteed outcomes.</p></main></body></html>',
        headers={"Cache-Control": "no-store, private",
                 "Referrer-Policy": "no-referrer",
                 "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'"},
    )


@csrf_protect
@require_http_methods(["GET", "POST"])
def signal_free_confirm(request, token):
    subscriber = _validated_token(token, "confirm")
    if subscriber is None or subscriber.status != "pending":
        return _answer({"ok": False, "detail": "Confirmation link invalid or expired."}, 404)
    if request.method == "GET":
        return _confirmation_page(
            request, "Confirm free educational updates",
            "Confirm your opt-in to occasional historical, non-actionable research education. No paid subscription is created.",
            "Confirm free registration",
        )
    if not _smtp_ready():
        return _answer({"ok": False, "detail": "Verified registration is not currently available."}, 503)
    updated = MojSignalFreeSubscription.objects.filter(
        pk=subscriber.pk, status="pending", nonce=subscriber.nonce,
    ).update(status="confirmed", confirmed_at=timezone.now(), unsubscribed_at=None)
    if not updated:
        return _answer({"ok": False, "detail": "Confirmation link invalid or expired."}, 404)
    return _answer({"ok": True, "status": "confirmed", "paid_entitlement": False})


@csrf_protect
@require_http_methods(["GET", "POST"])
def signal_free_unsubscribe(request, token):
    subscriber = _validated_token(token, "unsubscribe")
    if subscriber is None or subscriber.status != "confirmed":
        return _answer({"ok": False, "detail": "Unsubscribe link invalid or expired."}, 404)
    if request.method == "GET":
        return _confirmation_page(
            request, "Stop educational research updates",
            "You can stop free educational updates without payment, account login or an email to support.",
            "Unsubscribe",
        )
    updated = MojSignalFreeSubscription.objects.filter(
        pk=subscriber.pk, status="confirmed", nonce=subscriber.nonce,
    ).update(status="unsubscribed", unsubscribed_at=timezone.now(),
             nonce=secrets.token_urlsafe(24))
    if not updated:
        return _answer({"ok": False, "detail": "Unsubscribe link invalid or expired."}, 404)
    return _answer({"ok": True, "status": "unsubscribed", "paid_entitlement": False})
