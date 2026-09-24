from django.db import transaction

from .models import ApprovalRequest, AgentTask, AuditLog


class ApprovalService:
    """Owner approval lifecycle. Approval never executes an action by itself."""

    @transaction.atomic
    def decide(self, approval_id, approved, actor_id=None, note="", actor_type="owner"):
        approval = ApprovalRequest.objects.select_for_update().get(pk=approval_id)
        if approval.status != "pending":
            raise ValueError("Approval is no longer pending")
        if not isinstance(approved, bool):
            raise ValueError("Approval decision must be a boolean")
        if actor_type == "owner" and actor_id is not None and approval.requested_by_id != actor_id:
            raise ValueError("Only the designated owner can make this approval decision")

        approval.status = "approved" if approved else "rejected"
        approval.decision_note = str(note or "")[:5000]
        approval.save(update_fields=["status", "decision_note", "updated_at"])

        task = None
        if approval.target_type == "AgentTask":
            task = AgentTask.objects.select_for_update().filter(pk=approval.target_id).first()
            if task:
                if approved and task.status != "blocked":
                    raise ValueError("Only a blocked task can be released by approval")
                if not approved and task.status not in {"blocked", "queued"}:
                    raise ValueError("Rejected approval cannot alter an executing or terminal task")
                task.status = "queued" if approved else "cancelled"
                task.save(update_fields=["status", "updated_at"])

        AuditLog.objects.create(
            actor_type=str(actor_type or "owner")[:30],
            actor_id=str(actor_id or ""),
            action="approval_decision",
            target_type="ApprovalRequest",
            target_id=str(approval.pk),
            after_state={
                "approved": approved,
                "task_status": getattr(task, "status", None),
            },
            trace_id=f"approval-{approval.pk}",
        )
        return approval
