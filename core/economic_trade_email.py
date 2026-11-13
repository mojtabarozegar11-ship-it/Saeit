"""Company trade mailbox: policy-gated email outbox for Economic Master Agent."""
import hashlib
import uuid

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction

from .economic_trade_models import TradeEmailAudit, TradeEmailOutbox, TradeMailbox
from .models import ApprovalGrant
from .trade_approval_scope import trade_email_approval_matches, trade_email_fingerprint


TRADE_EMAIL_POLICY = {
    "company_mailbox_only": True,
    "third_party_credentials": False,
    "outbox_before_send": True,
    "idempotency_required": True,
    "audit_required": True,
    "real_send_default": False,
    "owner_approval_for_binding_commitments": True,
    "durable_dispatch_reservation_before_smtp": True,
    "unknown_delivery_requires_manual_reconciliation": True,
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


def _finalize_dispatch(outbox_id, *, status, error=""):
    """Persist one terminal delivery assessment; do not requeue uncertainty."""
    with transaction.atomic():
        item = TradeEmailOutbox.objects.select_for_update().get(pk=outbox_id)
        if item.status != "dispatching":
            raise RuntimeError("TRADE_EMAIL_DISPATCH_STATE_CHANGED_RECONCILE_REQUIRED")
        item.status = status
        item.error = error[:1000]
        item.save(update_fields=["status", "error", "updated_at"])
        TradeEmailAudit.objects.create(
            outbox=item,
            action=status,
            trace_id=_trace_id(),
            metadata={"provider": "django-email", "delivery_confirmed": status == "sent"},
        )
        return item


def send_queued_trade_email(outbox_id, *, grant_id=None):
    """Use a durable one-shot reservation and exact owner grant before SMTP.

    Reserve dispatch and consume permission in one committed transaction.
    SMTP is called only AFTER commit. If SMTP reports an exception or an
    ambiguous result, preserve 'delivery_unknown' and prohibit automatic
    resend. A crash after reservation leaves 'dispatching' for reconciliation
    rather than restoring an unsafe 'queued' state.
    """
    if isinstance(grant_id, bool) or not isinstance(grant_id, int) or grant_id <= 0:
        raise RuntimeError("Trade email requires an exact owner grant")
    # An outer atomic block would postpone the reservation commit until
    # AFTER SMTP, destroying the durability guarantee.
    if transaction.get_connection().in_atomic_block:
        raise RuntimeError("TRADE_EMAIL_DISPATCH_REQUIRES_NO_OUTER_TRANSACTION")

    with transaction.atomic():
        outbox = (
            TradeEmailOutbox.objects.select_for_update()
            .select_related("mailbox")
            .get(pk=outbox_id)
        )
        if outbox.status != "queued":
            raise RuntimeError(f"Trade email is not queued (status={outbox.status}).")
        grant = ApprovalGrant.objects.select_related("approval").filter(pk=grant_id).first()
        if (grant is None or grant.approval.target_type != "TradeEmailOutbox"
                or not trade_email_approval_matches(grant.approval, outbox)):
            raise RuntimeError("TRADE_EMAIL_EXACT_OUTBOX_APPROVAL_REQUIRED")
        scope = {
            "action": "external_write",
            "outbox_id": outbox.pk,
            "message_sha256": trade_email_fingerprint(outbox),
        }
        if not getattr(settings, "TRADE_EMAIL_ENABLED", False):
            raise RuntimeError("TRADE_EMAIL_ENABLED is false; real sending is disabled.")
        if not outbox.mailbox.active or not outbox.mailbox.allow_outbound:
            raise RuntimeError("Trade mailbox outbound policy is disabled.")
        if not outbox.mailbox.email_address:
            raise RuntimeError("Company trade mailbox has no configured sender address.")
        from .approval import ApprovalService
        ApprovalService().authorize_grant(grant_id, scope)

        message = EmailMessage(
            subject=outbox.subject,
            body=outbox.body,
            from_email=outbox.mailbox.email_address,
            to=[outbox.recipient],
            reply_to=[outbox.mailbox.email_address],
        )
        outbox.status = "dispatching"
        outbox.save(update_fields=["status", "updated_at"])
        TradeEmailAudit.objects.create(
            outbox=outbox,
            action="dispatch_reserved",
            trace_id=_trace_id(),
            metadata={
                "grant_id": grant_id,
                "sha256": scope["message_sha256"],
                "provider": "django-email",
            },
        )
        persisted_id = outbox.pk
    # The reservation and one-time permission MUST be committed here.
    try:
        count = message.send(fail_silently=False)
    except Exception as exc:
        _finalize_dispatch(
            persisted_id, status="delivery_unknown",
            error=f"SMTP attempt raised {type(exc).__name__}; manual reconciliation required",
        )
        raise RuntimeError("TRADE_EMAIL_DELIVERY_UNKNOWN_RECONCILE_REQUIRED") from exc
    return _finalize_dispatch(
        persisted_id,
        status="sent" if count == 1 else "delivery_unknown",
        error="" if count == 1 else "Provider did not confirm one delivery; reconcile before further action",
    )
