"""Database-backed, multi-process rate limits dedicated to MojPlayWin checkout.

No X-Forwarded-For trust. Uses the REMOTE_ADDR supplied by the web server.
This limits accidental invoice floods; a separate WAF/CAPTCHA is still
required for public deployment. A database outage fails closed.
"""
import hashlib
import ipaddress
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone

from .mojplaywin_crypto_models import MojCryptoThrottle


def _identity(request, *, user=False, invoice=None):
    if invoice is not None:
        raw = "invoice:" + str(invoice)
    elif user:
        if not request.user.is_authenticated:
            raise ValueError("Authenticated user required")
        raw = "user:" + str(request.user.pk)
    else:
        address = request.META.get("REMOTE_ADDR", "")
        try:
            raw = "ip:" + ipaddress.ip_address(address).compressed
        except ValueError:
            raw = "ip:unknown"
    salt = settings.SECRET_KEY
    return hashlib.sha256((salt + "\0" + raw).encode("utf-8")).hexdigest()


def check_limit(request, action, limit, window_seconds, *, user=False, invoice=None):
    """Atomically consume one quota unit; return 429 response if exceeded.

    The database unique constraint and conditional UPDATE provide an atomic
    cross-worker counter without relying on per-process Django LocMemCache.
    """
    key = _identity(request, user=user, invoice=invoice)
    seconds = int(timezone.now().timestamp())
    bucket = seconds // window_seconds
    with transaction.atomic():
        row, _ = MojCryptoThrottle.objects.get_or_create(
            action=action, identity_hash=key, bucket=bucket,
            defaults={"attempts": 0},
        )
        consumed = MojCryptoThrottle.objects.filter(
            pk=row.pk, attempts__lt=limit,
        ).update(attempts=F("attempts") + 1)
    if consumed:
        return None
    response = HttpResponse("Too many requests. Please try again later.", status=429)
    response["Retry-After"] = str(window_seconds - seconds % window_seconds)
    response["Cache-Control"] = "no-store"
    return response
