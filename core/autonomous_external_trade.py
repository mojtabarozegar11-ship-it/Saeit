"""Pending owner approval for one exact external trade email.

Creating a request never approves, sends or issues execution authority.
A completed owner decision and a short-lived one-use grant are separate.
"""
from django.contrib.auth import get_user_model
from django.db import transaction

from core.approval import ApprovalService
from core.economic_trade_email import mailbox_status, send_queued_trade_email
from core.economic_trade_models import TradeEmailOutbox
from core.models import ApprovalGrant, ApprovalRequest, AuditLog
from core.trade_approval_scope import (
    exact_trade_email_reason, trade_email_fingerprint,
    trade_email_approval_matches,
)


@transaction.atomic
def authorize_external_trade(
    *, owner_id, outbox_id=None,
    note="Owner approval is required before external trade action.",
):
    """Request review of one existing queued message, never blanket consent."""
    if isinstance(outbox_id, bool) or not isinstance(outbox_id, int) or outbox_id <= 0:
        raise ValueError("A specific positive outbox_id is required for owner review")
    owner = get_user_model().objects.get(pk=owner_id, is_active=True)
    outbox = (
        TradeEmailOutbox.objects.select_related("mailbox")
        .filter(pk=outbox_id, status="queued", mailbox__code="company-trade")
        .first()
    )
    if outbox is None:
        raise ValueError("Only an existing queued company-trade email can be reviewed")
    return ApprovalRequest.objects.create(
        action_type="external_write",
        target_type="TradeEmailOutbox",
        target_id=str(outbox.pk),
        reason=exact_trade_email_reason(outbox),
        risk="high",
        status="pending",
        requested_by=owner,
    )


def execute_one_authorized_outbox(*, grant_id):
    """Send only the exact message reviewed by the owner, never queue.first()."""
    grant = ApprovalGrant.objects.select_related("approval").get(pk=grant_id)
    approval = grant.approval
    if approval.target_type != "TradeEmailOutbox":
        raise RuntimeError("TRADE_EMAIL_EXACT_OUTBOX_APPROVAL_REQUIRED")
    try:
        outbox_id = int(approval.target_id)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("TRADE_EMAIL_INVALID_OUTBOX_ID") from exc
    outbox = (
        TradeEmailOutbox.objects.select_related("mailbox")
        .filter(pk=outbox_id)
        .first()
    )
    if not trade_email_approval_matches(approval, outbox):
        raise RuntimeError("TRADE_EMAIL_REVIEWED_CONTENT_CHANGED_OR_NOT_QUEUED")
    scope = {
        "action": "external_write",
        "outbox_id": outbox.pk,
        "message_sha256": trade_email_fingerprint(outbox),
    }
    status = mailbox_status()
    if not status["configured"] or not status["active"]:
        raise RuntimeError("Trade sender is not configured or outbound sending is disabled.")
    if not outbox.mailbox.active or not outbox.mailbox.allow_outbound:
        raise RuntimeError("Trade mailbox outbound policy is disabled.")

    # The locked sender itself consumes the one-time grant; no direct caller
    # can bypass it merely by enabling email in the environment.
    sent = send_queued_trade_email(outbox.pk, grant_id=grant_id)
    AuditLog.objects.create(
        actor_type="economic-agent",
        actor_id="mojtaba.bot.ai",
        action="external_trade_email_sent",
        target_type="TradeEmailOutbox",
        target_id=str(sent.pk),
        after_state={"status": sent.status},
        trace_id=f"trade-send-{sent.pk}",
    )
    return sent
