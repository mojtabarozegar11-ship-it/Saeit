from django.db import transaction
from .models import ApprovalRequest, AgentTask, AuditLog

class ApprovalService:
    """Owner approval lifecycle. Approval never executes an action by itself."""
    @transaction.atomic
    def decide(self, approval_id, approved, actor_id=None, note=""):
        approval = ApprovalRequest.objects.select_for_update().get(pk=approval_id)
        if approval.status != "pending":
            raise ValueError("Approval is no longer pending")
        approval.status = "approved" if approved else "rejected"
        approval.reason = note or approval.reason
        approval.save(update_fields=["status", "reason", "updated_at"])
        task = AgentTask.objects.filter(pk=approval.target_id).first()
        if task:
            task.status = "queued" if approved else "cancelled"
            task.save(update_fields=["status", "updated_at"])
        AuditLog.objects.create(
            actor_type="owner", actor_id=str(actor_id or ""), action="approval_decision",
            target_type="ApprovalRequest", target_id=str(approval.pk),
            after_state={"approved": approved, "task_status": getattr(task, "status", None)},
        )
        return approval
