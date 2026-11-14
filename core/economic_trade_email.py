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


def send_queued_trade_email(outbox_id, *, grant_id=None):
    """Claim ONE exact owner-approved message before SMTP; never auto-replay.

    "Submitted" means only the Django transport returned one accepted message.
    It is not proof of inbox delivery, customer consent or realized revenue.
    A transport exception can occur *after* a remote side effect; failed or
    unknown sends remain terminal for this attempt pending reconciliation.
    """
    from core.approval import ApprovalService
    from core.trade_outbox_scope import message_digest

    if type(outbox_id) is not int or outbox_id < 1:
        raise ValueError("OUTBOX_ID_INVALID")
    # Validate all nonfinancial preconditions before claiming the single-use
    # grant. In particular, never burn approval to discover SMTP is disabled.
    with transaction.atomic():
        outbox = (
            TradeEmailOutbox.objects.select_for_update()
            .select_related("mailbox")
            .get(pk=outbox_id)
        )
        if outbox.status != "queued":
            raise RuntimeError(f"Trade email is not queued (status={outbox.status}).")
        if type(grant_id) is not int or grant_id < 1:
            raise RuntimeError("OWNER_GRANT_REQUIRED")
        configured_sender = getattr(settings, "COMPANY_TRADE_EMAIL", "")
        if not getattr(settings, "TRADE_EMAIL_ENABLED", False):
            raise RuntimeError("TRADE_EMAIL_ENABLED is false; real sending is disabled.")
        if (
            type(configured_sender) is not str
            or not configured_sender
            or not outbox.mailbox.active
            or not outbox.mailbox.allow_outbound
            or not outbox.mailbox.require_policy_gate
            or outbox.mailbox.code != "company-trade"
            or not outbox.mailbox.email_address
            or outbox.mailbox.email_address.casefold() != configured_sender.casefold()
        ):
            raise RuntimeError("Company outbound sender policy is not configured.")
        digest = message_digest(outbox)
        scope = {
            "action": "external_write",
            "outbox_id": outbox.pk,
            "message_digest": digest,
        }
        grant = ApprovalService().authorize_grant(grant_id, scope)
        # Mark an in-flight attempt *before* any external effect, outside of
        # which it may never become queued again automatically.
        outbox.status = "sending"
        outbox.save(update_fields=["status", "updated_at"])
        TradeEmailAudit.objects.create(
            outbox=outbox,
            action="sending_claimed",
            trace_id=_trace_id(),
            metadata={"grant_id": grant.pk, "message_digest": digest},
        )

    # The DB claim above is committed. An uncertain send is not retryable.
    try:
        message = EmailMessage(
            subject=outbox.subject,
            body=outbox.body,
            from_email=outbox.mailbox.email_address,
            to=[outbox.recipient],
            reply_to=[outbox.mailbox.email_address],
        )
        count = message.send(fail_silently=False)
        if count != 1:
            raise RuntimeError("OUTBOX_PROVIDER_ACCEPTANCE_UNCERTAIN")
    except Exception as exc:
        with transaction.atomic():
            TradeEmailOutbox.objects.filter(pk=outbox.pk, status="sending").update(
                status="delivery_uncertain",
            )
            TradeEmailAudit.objects.create(
                outbox=outbox,
                action="delivery_uncertain",
                trace_id=_trace_id(),
                metadata={"error_type": type(exc).__name__, "automatic_retry": False},
            )
        raise RuntimeError("OUTBOX_DELIVERY_RECONCILIATION_REQUIRED") from exc

    with transaction.atomic():
        updated = TradeEmailOutbox.objects.filter(pk=outbox.pk, status="sending").update(
            status="delivery_submitted_unverified",
        )
        if updated != 1:
            raise RuntimeError("OUTBOX_CLAIM_LOST_RECONCILE_PROVIDER")
        TradeEmailAudit.objects.create(
            outbox=outbox,
            action="provider_accepted_unverified",
            trace_id=_trace_id(),
            metadata={"provider": "django-email", "accepted_count": 1,
                      "delivery_verified": False},
        )
    outbox.refresh_from_db()
    return outbox
