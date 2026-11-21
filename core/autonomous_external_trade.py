"""Owner-approved external commerce bridge for the autonomous master agent.

This module never self-approves an external trade action.  Creating a request
and approving it are intentionally separate operations so an autonomous agent
cannot manufacture the owner's consent.
"""
from django.contrib.auth import get_user_model
from django.db import transaction

from core.approval import ApprovalService
from core.economic_trade_email import mailbox_status, send_queued_trade_email
from core.economic_trade_models import TradeEmailOutbox
from core.models import ApprovalRequest, AuditLog


@transaction.atomic
def authorize_external_trade(*, owner_id, note="Owner approval is required before any external trade action."):
    """Create a pending request; do not approve or grant execution authority.

    The function name is retained for compatibility, but it deliberately
    performs only the request step.  A separate, authenticated owner action
    must call ApprovalService.decide(..., approved=True) and then issue_grant.
    """
    owner = get_user_model().objects.get(pk=owner_id)
    return ApprovalRequest.objects.create(
        action_type="external_write",
        target_type="TradeMailbox",
        target_id="company-trade",
        reason="Autonomous master agent requires audited outbound trade execution.",
        risk="high",
        status="pending",
        requested_by=owner,
    )


def execute_one_authorized_outbox(*, grant_id):
    """Consume one owner-issued grant and send one already-queued message."""
    ApprovalService().authorize_grant(
        grant_id, {"action": "external_write", "target": "company-trade"}
    )
    status = mailbox_status()
    if not status["configured"]:
        raise RuntimeError("Trade sender is not configured.")
    candidate = (
        TradeEmailOutbox.objects.select_related("mailbox")
        .filter(status="queued")
        .order_by("created_at")
        .first()
    )
    if candidate is None:
        raise RuntimeError("No evidence-backed queued recipient exists; refusing fabricated outreach.")
    sent = send_queued_trade_email(candidate.pk)
    AuditLog.objects.create(
        actor_type="economic-agent",
        actor_id="mojtaba-bot-ai",
        action="external_trade_email_sent",
        target_type="TradeEmailOutbox",
        target_id=str(sent.pk),
        after_state={"status": sent.status},
        trace_id=f"trade-send-{sent.pk}",
    )
    return sent
