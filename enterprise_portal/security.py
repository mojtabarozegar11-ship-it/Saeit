"""Persistent private-office login throttling.

The throttle key is a keyed one-way digest of REMOTE_ADDR + normalized username,
never a credential or plain IP. Shared database state works across WSGI workers.
Ingress-level per-IP rate limits remain an additional production requirement.
"""
from datetime import timedelta

from django.core.signing import salted_hmac
from django.db import transaction
from django.utils import timezone

from .models import OfficeLoginFailure

MAX_FAILURES = 5
WINDOW = timedelta(minutes=15)
BLOCK_FOR = timedelta(minutes=15)


def _login_key(request, username):
    address = str(request.META.get("REMOTE_ADDR", "unknown"))[:80]
    normalized = str(username).strip().casefold()[:200]
    return salted_hmac(
        "zomorod-private-office-2026",
        f"{address}|{normalized}",
    ).hexdigest()


def login_is_blocked(request, username):
    if not username:
        return False
    now = timezone.now()
    row = OfficeLoginFailure.objects.filter(
        key=_login_key(request, username),
    ).first()
    return bool(row and row.blocked_until and row.blocked_until > now)


@transaction.atomic
def register_failed_login(request, username):
    if not username:
        return
    key = _login_key(request, username)
    now = timezone.now()
    row, created = OfficeLoginFailure.objects.select_for_update().get_or_create(
        key=key,
        defaults={"failed_count": 0, "last_failed_at": now},
    )
    # Keep the lock until expiration even when additional requests arrive.
    if row.blocked_until and row.blocked_until > now:
        return
    if created or now - row.last_failed_at > WINDOW:
        row.failed_count = 0
        row.blocked_until = None
    row.failed_count += 1
    row.last_failed_at = now
    if row.failed_count >= MAX_FAILURES:
        row.blocked_until = now + BLOCK_FOR
    row.save(update_fields=("failed_count", "last_failed_at", "blocked_until"))


def clear_login_failures(request, username):
    if username:
        OfficeLoginFailure.objects.filter(key=_login_key(request, username)).delete()
