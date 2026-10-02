"""Owner-authorized external commerce bridge for the autonomous master agent."""
from django.contrib.auth import get_user_model
from django.db import transaction
from core.approval import ApprovalService
from core.economic_trade_email import mailbox_status, send_queued_trade_email
from core.economic_trade_models import TradeEmailOutbox
from core.models import ApprovalRequest, AuditLog

@transaction.atomic
def authorize_external_trade(*, owner_id, note="Owner authorized autonomous external trade."):
    owner=get_user_model().objects.get(pk=owner_id)
    req=ApprovalRequest.objects.create(action_type="external_write",target_type="TradeMailbox",
        target_id="company-trade",reason="Autonomous master agent requires audited outbound trade execution.",
        risk="high",status="pending",requested_by=owner)
    ApprovalService().decide(req.pk,True,actor_id=owner.pk,note=note,actor_type="owner")
    grant=ApprovalService().issue_grant(req.pk,owner.pk,scope={"action":"external_write","target":"company-trade"},ttl_seconds=900)
    return req,grant

def execute_one_authorized_outbox(*, grant_id):
    ApprovalService().authorize_grant(grant_id,{"action":"external_write","target":"company-trade"})
    status=mailbox_status()
    if not status["configured"]:
        raise RuntimeError("Trade sender is not configured.")
    candidate=TradeEmailOutbox.objects.select_related("mailbox").filter(status="queued").order_by("created_at").first()
    if candidate is None:
        raise RuntimeError("No evidence-backed queued recipient exists; refusing fabricated outreach.")
    sent=send_queued_trade_email(candidate.pk)
    AuditLog.objects.create(actor_type="economic-agent",actor_id="economic-master-agent",
        action="external_trade_email_sent",target_type="TradeEmailOutbox",target_id=str(sent.pk),
        after_state={"status":sent.status},trace_id=f"trade-send-{sent.pk}")
    return sent
