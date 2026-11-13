from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from django.contrib.auth import get_user_model
from .chat_operation_security import is_authorized_chat_operator
from .task_approval_scope import approval_covers_task
from .services import normalize_action

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
        # Do not accept an absent actor or a caller-supplied actor_type
        # such as "system"/"agent" to bypass the designated owner check.
        # API authentication still happens independently at the view boundary.
        if actor_type != "owner" or actor_id is None or approval.requested_by_id != actor_id:
            raise ValueError("Only the designated owner can make this approval decision")
        if not get_user_model().objects.filter(pk=actor_id, is_active=True).exists():
            raise ValueError("Only an active designated owner can decide an approval")
        if approval.target_type == "ChatOperation":
            operator = get_user_model().objects.filter(pk=actor_id).first() if actor_id is not None else None
            if not is_authorized_chat_operator(operator) or approval.requested_by_id != actor_id:
                raise ValueError("Chat operations require an active superuser owner")

        approval.status = "approved" if approved else "rejected"
        approval.decision_note = str(note or "")[:5000]
        approval.save(update_fields=["status", "decision_note", "updated_at"])

        task = None
        article = None
        if approval.target_type == "AgentTask":
            task = AgentTask.objects.select_for_update().filter(pk=approval.target_id).first()
            # A deleted/nonexistent task must never receive an approval token
            # that could be reused if its numeric ID appears again later.
            # Rejection still permits the owner to close an orphan request.
            if task is None and approved:
                raise ValueError("Approval target task no longer exists")
            if task:
                # Approval must be bound to the task's current action and risk.
                # This also prevents a mismatched rejection from cancelling a
                # legitimate task. transaction.atomic rolls back the decision.
                if not approval_covers_task(approval, task):
                    raise ValueError("Approval action or risk does not match task")
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


    @staticmethod
    def _validate_grant_scope(approval, scope):
        """One approval may authorize only its own action and target."""
        if not isinstance(scope, dict):
            raise ValueError("Execution grant scope must be an object")
        action = normalize_action(scope.get("action"))
        if not action or action != normalize_action(approval.action_type):
            raise ValueError("Execution grant action must match approved action")
        if approval.target_type == "AgentTask":
            task = AgentTask.objects.filter(pk=approval.target_id).first()
            if task is None or not approval_covers_task(approval, task):
                raise ValueError("Execution grant task is missing or changed")
            if "task_id" in scope and str(scope["task_id"]) != str(task.pk):
                raise ValueError("Execution grant task scope mismatch")
            if "target" in scope and scope["target"] != f"task:{task.pk}":
                raise ValueError("Execution grant target scope mismatch")
            if "run_id" in scope and (
                    not isinstance(task.input_data, dict)
                    or scope["run_id"] != task.input_data.get("run_id")):
                raise ValueError("Execution grant run scope mismatch")
            if scope.get("paid_model") is True and "run_id" not in scope:
                raise ValueError("Paid-model grant requires bound run_id")
        elif approval.target_type == "Order":
            if scope.get("target") != f"order:{approval.target_id}":
                raise ValueError("Execution grant order target mismatch")
        elif approval.target_type == "TradeMailbox":
            if scope.get("target") != approval.target_id:
                raise ValueError("Execution grant mailbox target mismatch")

    @transaction.atomic
    def issue_grant(self, approval_id, actor_id, scope=None, ttl_seconds=300):
        """Convert an approved request into a short-lived, one-time scoped grant."""
        approval = ApprovalRequest.objects.select_for_update().get(pk=approval_id)
        if approval.status != "approved":
            raise ValueError("Only an approved request can issue an execution grant")
        if approval.requested_by_id != actor_id or not get_user_model().objects.filter(
                pk=actor_id, is_active=True).exists():
            raise ValueError("Only the active designated owner can issue an execution grant")
        bounded_scope = dict(scope or {})
        self._validate_grant_scope(approval, bounded_scope)
        try:
            ttl = max(30, min(int(ttl_seconds), 900))
        except (TypeError, ValueError):
            raise ValueError("ttl_seconds must be an integer")
        now = timezone.now()
        grant = ApprovalGrant.objects.create(
            approval=approval,
            actor_id=actor_id,
            scope=bounded_scope,
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
        if grant.approval.status != "approved":
            raise ValueError("Execution grant approval is no longer approved")
        if not grant.actor.is_active:
            raise ValueError("Execution grant owner is inactive")
        self._validate_grant_scope(grant.approval, grant.scope)
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
