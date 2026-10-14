"""Checkout event notifications for the isolated MojPlayWin native-coin app.

Disabled unless MPW_NATIVE_EVENT_ENABLED and approved HTTPS/HMAC config exist.
After committing a pending invoice, sends a signed event to wake a VPS reader.
NO AI API, no wallet transfer, and no customer data is sent.
"""
import logging
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction

from scripts.mojplaywin_purchase_events import make_event, signed_message, EventRejected

logger = logging.getLogger("mpw_native_checkout.purchase_events")


class NotificationUnavailable(ValueError):
    pass


def send_invoice_event(invoice, *, action, opener=urlopen):
    """Return disabled/delivered. Reject unknown/unsafe remote destinations."""
    if getattr(settings, "MPW_NATIVE_EVENT_ENABLED", False) is not True:
        return "disabled"

    transport = getattr(settings, "MPW_NATIVE_EVENT_TRANSPORT", "https")
    if transport == "unix":
        secret = getattr(settings, "MPW_NATIVE_EVENT_SECRET", "")
        socket_path = getattr(settings, "MPW_NATIVE_EVENT_SOCKET", "")
        if not isinstance(secret, str) or len(secret.encode("utf-8")) < 32:
            raise NotificationUnavailable("Missing private event signing secret")
        if not isinstance(socket_path, str) or not socket_path.startswith("/"):
            raise NotificationUnavailable("Missing absolute private Unix socket")
        try:
            payload = make_event(
                action=action, invoice_id=invoice.pk, order_id=invoice.order_id,
                asset=invoice.asset, expires_at_epoch=int(invoice.expires_at.timestamp()),
            )
            body, signature = signed_message(payload, secret.encode("utf-8"))
            from scripts.mojplaywin_cpanel_local_event_worker import socket_request
            return socket_request(socket_path, body, signature)
        except (EventRejected, OSError, ValueError) as exc:
            raise NotificationUnavailable("Local event receiver unavailable") from exc
    if transport != "https":
        raise NotificationUnavailable("Unknown event transport")

    url = getattr(settings, "MPW_NATIVE_EVENT_URL", "")
    allowed_host = getattr(settings, "MPW_NATIVE_EVENT_HOST", "")
    secret = getattr(settings, "MPW_NATIVE_EVENT_SECRET", "")
    if not isinstance(url, str) or not isinstance(allowed_host, str):
        raise NotificationUnavailable("Purchase notification endpoint missing")
    try:
        parsed = urlsplit(url)
        allowed = (
            parsed.scheme == "https" and parsed.hostname is not None
            and parsed.hostname.lower() == allowed_host.lower()
            and parsed.username is None and parsed.password is None
            and parsed.query == "" and parsed.fragment == ""
            and parsed.port in (None, 443)
            and parsed.path == "/api/mpw/native-watch-event"
        )
    except ValueError as exc:
        raise NotificationUnavailable("Invalid HTTPS event URL") from exc
    if not allowed:
        raise NotificationUnavailable("Unapproved event endpoint")
    if not isinstance(secret, str) or len(secret.encode("utf-8")) < 32:
        raise NotificationUnavailable("Missing HMAC notification secret")

    try:
        payload = make_event(
            action=action, invoice_id=invoice.pk, order_id=invoice.order_id,
            asset=invoice.asset, expires_at_epoch=int(invoice.expires_at.timestamp()),
        )
        body, signature = signed_message(payload, secret.encode("utf-8"))
    except (EventRejected, TypeError, ValueError) as exc:
        raise NotificationUnavailable("Unsafe invoice notification") from exc

    request = Request(
        url, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "X-MPW-Signature": signature,
            "X-MPW-Event-Type": action,
            "User-Agent": "MojPlayWin-Native-Checkout/1",
        },
    )
    try:
        with opener(request, timeout=3) as response:
            if response.status != 200:
                raise NotificationUnavailable("Watcher did not acknowledge event")
            response.read(256)
    except (OSError, TimeoutError, ValueError) as exc:
        raise NotificationUnavailable("Watcher event delivery failed") from exc
    return "delivered"



def dispatch_queued_watch_event(invoice_id, *, sender=None):
    """Retry one durable alert with a DB row lock. Never marks orders paid."""
    from datetime import timedelta
    from django.utils import timezone
    from .models import NativeWatchOutbox

    if getattr(settings, "MPW_NATIVE_EVENT_ENABLED", False) is not True:
        return "disabled"
    if sender is None:
        sender = send_invoice_event
    with transaction.atomic():
        entry = (
            NativeWatchOutbox.objects.select_for_update()
            .select_related("invoice")
            .filter(invoice_id=invoice_id, state="pending").first()
        )
        if entry is None:
            return "nothing_queued"
        now = timezone.now()
        if entry.next_attempt_at and entry.next_attempt_at > now:
            return "backoff"
        try:
            status = sender(entry.invoice, action=entry.action)
            if status != "delivered":
                raise NotificationUnavailable("Receiver did not acknowledge")
        except (NotificationUnavailable, OSError, ValueError):
            entry.attempts = min(65535, entry.attempts + 1)
            wait = min(300, 2 ** min(8, entry.attempts))
            entry.next_attempt_at = now + timedelta(seconds=wait)
            entry.save(update_fields=[
                "attempts", "next_attempt_at", "updated_at",
            ])
            return "retry_queued"
        entry.state = "delivered"
        entry.delivered_at = now
        entry.next_attempt_at = None
        entry.save(update_fields=[
            "state", "delivered_at", "next_attempt_at", "updated_at",
        ])
        return "delivered"


def flush_pending_watch_events(*, limit=20):
    """Bounded local-database recovery only; zero requests when queue empty."""
    from django.db.models import Q
    from django.utils import timezone
    from .models import NativeWatchOutbox

    if getattr(settings, "MPW_NATIVE_EVENT_ENABLED", False) is not True:
        return {"state": "disabled", "attempted": 0}
    if type(limit) is not int or limit < 1 or limit > 100:
        raise ValueError("Unsafe outbox batch size")
    now = timezone.now()
    ids = list(
        NativeWatchOutbox.objects.filter(state="pending")
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .order_by("updated_at").values_list("invoice_id", flat=True)[:limit]
    )
    attempted = 0
    for invoice_id in ids:
        result = dispatch_queued_watch_event(invoice_id)
        if result in ("delivered", "retry_queued"):
            attempted += 1
    return {"state": "processed", "attempted": attempted}


def notify_after_commit(invoice, action):
    """Persist the latest required event BEFORE the parent's transaction commits.

    Failed deliveries remain in the private Django outbox for bounded retries.
    A 'close' replaces an unsent 'open', so stale alerts cannot reactivate
    an already-paid invoice.
    """
    from django.utils import timezone
    from .models import NativeWatchOutbox

    if action not in ("invoice_open", "invoice_closed"):
        raise NotificationUnavailable("Unknown invoice notification")
    NativeWatchOutbox.objects.update_or_create(
        invoice=invoice,
        defaults={
            "action": action,
            "state": "pending",
            "attempts": 0,
            "next_attempt_at": None,
            "delivered_at": None,
        },
    )

    def callback():
        try:
            dispatch_queued_watch_event(invoice.pk)
        except Exception:
            # Preserve outbox row for retry; never lose the purchase alert.
            logger.exception("watch_event_queue_delivery_deferred")
    transaction.on_commit(callback)
