"""Company trade mailbox: policy-gated email outbox for Economic Master Agent."""
import hashlib
import uuid

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction

from .economic_trade_models import TradeEmailAudit, TradeEmailOutbox, TradeMailbox


TRADE_EMAIL_POLICY = {
    "company_mailbox_only": True,
    "third_party_credentials": False,
    "outbox_before_send": True,
    "idempotency_required": True,
    "audit_required": True,
    "real_send_default": False,
    "owner_approval_for_binding_commitments": True,
}


def mailbox_status():
    address = getattr(settings, "COMPANY_TRADE_EMAIL", "")
    return {
        "configured": bool(address),
        "address": address,
        "active": bool(getattr(settings, "TRADE_EMAIL_ENABLED", False)),
        "policy": dict(TRADE_EMAIL_POLICY),
    }


def _trace_id():
    return uuid.uuid4().hex


def _idempotency(recipient, subject, body):
    raw = "|".join((recipient.strip().lower(), subject.strip(), body.strip()))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@transaction.atomic
def queue_trade_email(*, recipient, subject, body, trade_context=None):
    """Create an audited draft; never sends by itself."""
    mailbox, _ = TradeMailbox.objects.get_or_create(
        code="company-trade",
        defaults={
            "display_name": "Company International Trade Mailbox",
            "email_address": getattr(settings, "COMPANY_TRADE_EMAIL", ""),
        },
    )
    key = _idempotency(recipient, subject, body)
    outbox, created = TradeEmailOutbox.objects.get_or_create(
        idempotency_key=key,
        defaults={
            "mailbox": mailbox,
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "trade_context": trade_context or {},
            "status": "queued",
        },
    )
    TradeEmailAudit.objects.create(
        outbox=outbox,
        action="queued" if created else "deduplicated",
        trace_id=_trace_id(),
        metadata={"recipient_domain": recipient.rsplit("@", 1)[-1]},
    )
    return outbox


def send_queued_trade_email(outbox_id):
    """Send only when the explicit runtime gate is enabled and mailbox is active."""
    outbox = TradeEmailOutbox.objects.select_related("mailbox").get(pk=outbox_id)
    if not getattr(settings, "TRADE_EMAIL_ENABLED", False):
        raise RuntimeError("TRADE_EMAIL_ENABLED is false; real sending is disabled.")
    if not outbox.mailbox.active or not outbox.mailbox.allow_outbound:
        raise RuntimeError("Trade mailbox outbound policy is disabled.")
    if not outbox.mailbox.email_address:
        raise RuntimeError("Company trade mailbox has no configured sender address.")
    message = EmailMessage(
        subject=outbox.subject,
        body=outbox.body,
        from_email=outbox.mailbox.email_address,
        to=[outbox.recipient],
        reply_to=[outbox.mailbox.email_address],
    )
    count = message.send(fail_silently=False)
    outbox.status = "sent" if count == 1 else "failed"
    outbox.save(update_fields=["status", "updated_at"])
    TradeEmailAudit.objects.create(
        outbox=outbox,
        action=outbox.status,
        trace_id=_trace_id(),
        metadata={"provider": "django-email", "count": count},
    )
    return outbox
