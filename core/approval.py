from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .models import ApprovalRequest, AgentTask, ApprovalGrant, AuditLog, KnowledgeArticle, PaymentIntent, Product


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
        article = None
        if approval.target_type == "AgentTask":
            task = AgentTask.objects.select_for_update().filter(pk=approval.target_id).first()
            if task:
                if approved and task.status != "blocked":
                    raise ValueError("Only a blocked task can be released by approval")
                if not approved and task.status not in {"blocked", "queued"}:
                    raise ValueError("Rejected approval cannot alter an executing or terminal task")
                task.status = "queued" if approved else "cancelled"
                task.save(update_fields=["status", "updated_at"])
        elif approval.target_type == "KnowledgeArticle":
            article = KnowledgeArticle.objects.select_for_update().filter(pk=approval.target_id).first()
            if article is None:
                raise ValueError("Knowledge article no longer exists")
            if approved and article.published:
                raise ValueError("Knowledge article is already published")
            if approved:
                article.published = True
                article.save(update_fields=["published", "updated_at"])
        elif approval.target_type == "PaymentIntent":
            intent = PaymentIntent.objects.select_for_update().filter(pk=approval.target_id).first()
            if intent is None:
                raise ValueError("Payment intent no longer exists")
            if approved:
                if intent.status != "awaiting_approval":
                    raise ValueError("Payment intent is no longer awaiting approval")
                intent.status = "ready_for_gateway"
                intent.save(update_fields=["status", "updated_at"])
            elif intent.status == "awaiting_approval":
                intent.status = "rejected"
                intent.save(update_fields=["status", "updated_at"])
        elif approval.target_type == "Product":
            product = Product.objects.select_for_update().select_related("knowledge_article").filter(pk=approval.target_id).first()
            if product is None:
                raise ValueError("Product no longer exists")
            if approved and product.active:
                raise ValueError("Product is already active")
            if approved:
                if product.knowledge_article_id is None or not product.knowledge_article.published:
                    raise ValueError("Product requires published knowledge before activation")
                product.active = True
                product.save(update_fields=["active", "updated_at"])

        AuditLog.objects.create(
            actor_type=str(actor_type or "owner")[:30],
            actor_id=str(actor_id or ""),
            action="approval_decision",
            target_type="ApprovalRequest",
            target_id=str(approval.pk),
            after_state={
                "approved": approved,
                "task_status": getattr(task, "status", None),
                "article_published": getattr(article, "published", None),
                "product_active": getattr(locals().get("product"), "active", None),
                "payment_status": getattr(locals().get("intent"), "status", None),
            },
            trace_id=f"approval-{approval.pk}",
        )
        return approval


    @transaction.atomic
    def issue_grant(self, approval_id, actor_id, scope=None, ttl_seconds=300):
        """Convert an approved request into a short-lived, one-time scoped grant."""
        approval = ApprovalRequest.objects.select_for_update().get(pk=approval_id)
        if approval.status != "approved":
            raise ValueError("Only an approved request can issue an execution grant")
        if approval.requested_by_id != actor_id:
            raise ValueError("Only the designated owner can issue an execution grant")
        try:
            ttl = max(30, min(int(ttl_seconds), 900))
        except (TypeError, ValueError):
            raise ValueError("ttl_seconds must be an integer")
        now = timezone.now()
        grant = ApprovalGrant.objects.create(
            approval=approval,
            actor_id=actor_id,
            scope=dict(scope or {}),
            expires_at=now + timedelta(seconds=ttl),
        )
        AuditLog.objects.create(
            actor_type="owner",
            actor_id=str(actor_id),
            action="approval_grant_issued",
            target_type="ApprovalGrant",
            target_id=str(grant.pk),
            after_state={"approval_id": approval_id, "scope": grant.scope, "expires_at": grant.expires_at.isoformat()},
            trace_id=f"grant-{grant.pk}",
        )
        return grant

    @transaction.atomic
    def authorize_grant(self, grant_id, required_scope=None):
        """Atomically consume a valid grant exactly once."""
        grant = ApprovalGrant.objects.select_for_update().select_related("approval", "actor").get(pk=grant_id)
        if grant.used_at is not None:
            raise ValueError("Execution grant has already been used")
        if grant.expires_at <= timezone.now():
            raise ValueError("Execution grant has expired")
        required = dict(required_scope or {})
        if any(grant.scope.get(key) != value for key, value in required.items()):
            raise ValueError("Execution grant scope mismatch")
        grant.used_at = timezone.now()
        grant.save(update_fields=["used_at", "updated_at"])
        AuditLog.objects.create(
            actor_type="owner",
            actor_id=str(grant.actor_id),
            action="approval_grant_consumed",
            target_type="ApprovalGrant",
            target_id=str(grant.pk),
            after_state={"scope": grant.scope},
            trace_id=f"grant-{grant.pk}",
        )
        return grant
