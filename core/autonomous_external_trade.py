"""One-message owner-approved B2B contact bridge for mojtaba.bot.ai.

Never select an arbitrary queued email after consuming an unrelated grant.
An owner-scoped approval request is not permission to contact a recipient.
"""
from django.contrib.auth import get_user_model
from django.db import transaction

from core.approval import ApprovalService
from core.chat_operation_security import is_authorized_chat_operator
from core.economic_trade_email import send_queued_trade_email
from core.economic_trade_models import TradeEmailOutbox
from core.models import ApprovalGrant, ApprovalRequest, AuditLog
from core.trade_outbox_scope import message_digest, validate_outbox_for_owner_grant


@transaction.atomic
def authorize_external_trade(*, owner_id, outbox_id=None, note=""):
    """Create PENDING approval for an exact queued message. No actual email."""
    if type(owner_id) is not int or type(outbox_id) is not int or outbox_id < 1:
        raise ValueError("OWNER_AND_OUTBOX_IDS_REQUIRED")
    owner = get_user_model().objects.filter(pk=owner_id).first()
    if not is_authorized_chat_operator(owner):
        raise PermissionError("ACTIVE_OWNER_REQUIRED")
    outbox = (
        TradeEmailOutbox.objects.select_for_update()
        .select_related("mailbox")
        .get(pk=outbox_id)
    )
    digest = message_digest(outbox)
    scope = {"action": "external_write", "outbox_id": outbox_id,
             "message_digest": digest}
    validate_outbox_for_owner_grant(outbox, scope)
    # Private recipient information stays in the DB. Approval reason includes
    # only immutable identifiers/digest; a digest is not proof of consent.
    return ApprovalRequest.objects.create(
        action_type="external_write",
        target_type="TradeEmailOutbox",
        target_id=str(outbox.pk),
        reason=f"Bound B2B outbound message: sha256={digest}",
        risk="high",
        status="pending",
        requested_by=owner,
    )


def execute_one_authorized_outbox(*, grant_id):
    """Send exactly the outbox referenced by one valid grant, never the oldest."""
    if type(grant_id) is not int or grant_id < 1:
        raise ValueError("ONE_TIME_GRANT_ID_REQUIRED")
    grant = ApprovalGrant.objects.select_related("approval").get(pk=grant_id)
    scope = grant.scope
    if (
        type(scope) is not dict
        or scope.get("action") != "external_write"
        or type(scope.get("outbox_id")) is not int
        or grant.approval.target_type != "TradeEmailOutbox"
        or grant.approval.target_id != str(scope["outbox_id"])
    ):
        raise PermissionError("OUTBOX_GRANT_BINDING_INVALID")
    sent = send_queued_trade_email(scope["outbox_id"], grant_id=grant.pk)
    AuditLog.objects.create(
        actor_type="economic-agent",
        actor_id="mojtaba-bot-ai",
        action="external_trade_email_submitted_unverified",
        target_type="TradeEmailOutbox",
        target_id=str(sent.pk),
        after_state={
            "status": sent.status,
            "grant_id": grant.pk,
            "message_digest": scope["message_digest"],
            "delivery_verified": False,
            "customer_response_verified": False,
            "settled_revenue": None,
        },
        trace_id=f"trade-send-{sent.pk}-{grant.pk}",
    )
    return sent
