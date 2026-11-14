from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from django.contrib.auth import get_user_model
from .chat_operation_security import is_authorized_chat_operator
from .task_approval_scope import approval_covers_task
from .chat_operation_scope import validate_chat_operation_scope
from .grant_scope_policy import require_exact_grant_scope, require_exact_consumption_scope
from .trade_outbox_scope import validate_outbox_for_owner_grant
from .economic_trade_models import TradeEmailOutbox

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
        if actor_type != "owner" or actor_id is None or approval.requested_by_id != actor_id:
            raise ValueError("Only the designated owner can make this approval decision")
        if not get_user_model().objects.filter(pk=actor_id, is_active=True).exists():
            raise ValueError("Only an active designated owner can decide an approval")
        if approval.target_type in {"PaymentIntent", "Product"}:
            financial_owner = get_user_model().objects.filter(pk=actor_id).first()
            if not is_authorized_chat_operator(financial_owner):
                raise ValueError("Commerce approvals require the active designated superuser owner")
        if approval.target_type == "ChatOperation":
            operator = get_user_model().objects.filter(pk=actor_id).first() if actor_id is not None else None
            if not is_authorized_chat_operator(operator) or approval.requested_by_id != actor_id:
                raise ValueError("Chat operations require an active superuser owner")
            if approved:
                validate_chat_operation_scope(approval)

        approval.status = "approved" if approved else "rejected"
        approval.decision_note = str(note or "")[:5000]
        approval.save(update_fields=["status", "decision_note", "updated_at"])

        task = None
        article = None
        if approval.target_type == "AgentTask":
            task = AgentTask.objects.select_for_update().filter(pk=approval.target_id).first()
            if task is None:
                raise ValueError("Approval target task does not exist")
            if not approval_covers_task(approval, task):
                raise ValueError("Approval does not match target task action or risk")
            if task:
                # A prior attempt may have performed a side effect before
                # reporting a failure. A standard approval decision is NOT
                # a reconciliation receipt and must never reset its status.
                uncertain = (
                    task.status == "blocked" and (
                        task.attempt_count > 0
                        or (task.output_data or {}).get("requires_review") is True
                        or (task.output_data or {}).get("automatic_replay_allowed") is False
                    )
                )
                if uncertain:
                    raise ValueError(
                        "UNCERTAIN_TASK_EFFECT_REQUIRES_INDEPENDENT_RECONCILIATION"
                    )
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
            intent = PaymentIntent.objects.select_for_update().select_related("order").filter(pk=approval.target_id).first()
            if intent is None:
                raise ValueError("Payment intent no longer exists")
            purchased_item = intent.order.items.select_related("product").first()
            if (purchased_item is None or purchased_item.product.owner_id != actor_id
                    or intent.order.status != "pending"
                    or intent.amount != intent.order.total
                    or intent.currency != intent.order.currency):
                raise ValueError("Payment approval does not match designated product owner and pending order")
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
            if product.owner_id != actor_id:
                raise ValueError("Product approval requires its designated owner")
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
        """Issue ONE immutable action-bound and target-bound grant per approval.

        A different commercial operation requires a new independent request.
        The approval record is not a wildcard and no caller-provided ID is
        proof of an authenticated host session.
        """
        approval = (
            ApprovalRequest.objects.select_for_update()
            .select_related("requested_by")
            .get(pk=approval_id)
        )
        if approval.status != "approved":
            raise ValueError("Only an approved request can issue an execution grant")
        if type(actor_id) is not int or actor_id != approval.requested_by_id:
            raise ValueError("Only the designated owner can issue an execution grant")
        if not is_authorized_chat_operator(approval.requested_by):
            raise ValueError("A current active superuser is required for this grant")
        if type(ttl_seconds) is not int or not 30 <= ttl_seconds <= 900:
            raise ValueError("Grant TTL must be an integer between 30 and 900 seconds")
        approved_scope = require_exact_grant_scope(approval, scope)

        if approval.action_type == "knowledge_content_generation":
            task = AgentTask.objects.select_for_update().filter(
                pk=approval.target_id,
            ).first()
            input_data = task.input_data if task and isinstance(task.input_data, dict) else {}
            if (task is None
                    or task.action_type != "knowledge_content_generation"
                    or input_data.get("run_id") != approved_scope["run_id"]
                    or type(input_data.get("run_id")) is not int):
                raise ValueError("GRANT_PAID_MODEL_TASK_RUN_MISMATCH")

        if approval.action_type == "external_write":
            outbox = (
                TradeEmailOutbox.objects.select_for_update()
                .select_related("mailbox")
                .filter(pk=approval.target_id)
                .first()
            )
            if outbox is None:
                raise ValueError("GRANT_OUTBOX_NOT_FOUND")
            validate_outbox_for_owner_grant(outbox, approved_scope)

        # A one-time token is not enough if the SAME owner approval can mint
        # limitless fresh tokens. Serialize on approval row and deny reissues.
        if ApprovalGrant.objects.filter(approval=approval).exists():
            raise ValueError("GRANT_APPROVAL_ALREADY_ISSUED")
        now = timezone.now()
        grant = ApprovalGrant.objects.create(
            approval=approval,
            actor=approval.requested_by,
            scope=approved_scope,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        AuditLog.objects.create(
            actor_type="owner",
            actor_id=str(actor_id),
            action="approval_grant_issued",
            target_type="ApprovalGrant",
            target_id=str(grant.pk),
            after_state={
                "approval_id": approval_id,
                "action": approved_scope["action"],
                "scope": approved_scope,
                "expires_at": grant.expires_at.isoformat(),
            },
            trace_id=f"grant-{grant.pk}",
        )
        return grant

    @transaction.atomic
    def authorize_grant(self, grant_id, required_scope=None):
        """Atomically consume once, only for the original exact approved action."""
        grant = (
            ApprovalGrant.objects.select_for_update()
            .select_related("approval", "actor", "approval__requested_by")
            .get(pk=grant_id)
        )
        if grant.used_at is not None:
            raise ValueError("Execution grant has already been used")
        if (grant.approval.status != "approved"
                or grant.approval.requested_by_id != grant.actor_id
                or not is_authorized_chat_operator(grant.actor)):
            raise ValueError("GRANT_OWNER_OR_APPROVAL_NO_LONGER_VALID")
        # Reject a grant whose persisted scope was mutated after issuance.
        saved = require_exact_grant_scope(grant.approval, grant.scope)
        checked = require_exact_consumption_scope(saved, required_scope)
        if grant.expires_at <= timezone.now():
            raise ValueError("Execution grant has expired")
        if grant.approval.action_type == "knowledge_content_generation":
            task = AgentTask.objects.select_for_update().filter(
                pk=grant.approval.target_id,
            ).first()
            inputs = task.input_data if task and isinstance(task.input_data, dict) else {}
            if (task is None
                    or task.action_type != "knowledge_content_generation"
                    or inputs.get("run_id") != checked["run_id"]
                    or type(inputs.get("run_id")) is not int):
                raise ValueError("GRANT_PAID_MODEL_TASK_RUN_MISMATCH")
        if grant.approval.action_type == "external_write":
            outbox = (
                TradeEmailOutbox.objects.select_for_update()
                .select_related("mailbox")
                .filter(pk=grant.approval.target_id)
                .first()
            )
            if outbox is None:
                raise ValueError("GRANT_OUTBOX_NOT_FOUND")
            validate_outbox_for_owner_grant(outbox, checked)
        grant.used_at = timezone.now()
        grant.save(update_fields=["used_at", "updated_at"])
        AuditLog.objects.create(
            actor_type="owner",
            actor_id=str(grant.actor_id),
            action="approval_grant_consumed",
            target_type="ApprovalGrant",
            target_id=str(grant.pk),
            after_state={
                "approval_id": grant.approval_id,
                "scope": checked,
            },
            trace_id=f"grant-{grant.pk}",
        )
        return grant
