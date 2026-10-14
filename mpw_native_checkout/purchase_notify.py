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


def notify_after_commit(invoice, action):
    """Avoid blocking payment state on a transient downstream watcher outage."""
    def callback():
        try:
            send_invoice_event(invoice, action=action)
        except NotificationUnavailable:
            # A durable retry queue is required before production activation.
            logger.warning("wallet_event_send_failed kind=%s", action)
    transaction.on_commit(callback)
