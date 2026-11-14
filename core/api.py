from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .approval import ApprovalService
from .chat_operation_security import is_authorized_chat_operator
from .task_runtime import TaskExecutionError, TaskRuntime
from .task_reconciliation import (
    build_reconciliation_dossier, record_reconciliation_observation,
)
from .unified_bot_identity import BOT_CODE, EXECUTOR_RUNTIME_CODES


from .orchestrator import MasterAgent
from django.db import models, transaction, IntegrityError
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.utils import timezone
import hashlib
import hmac
import json
import re
from decimal import Decimal, InvalidOperation

from .models import (
    Agent, AgentCapability, AgentTask, ApprovalRequest, AuditLog, ChatMessage, ChatSession, Evidence, Finding,
    KnowledgeArticle, LedgerEntry, Order, OrderItem, PaymentIntent, PaymentWebhookEvent, Product, Report, ResearchProject, ResearchSource,
)
from .serializers import (
    AgentCapabilitySerializer, AgentSerializer, AgentTaskSerializer, ApprovalRequestSerializer, ChatMessageSerializer, ChatSessionSerializer,
    EvidenceSerializer, FindingSerializer, KnowledgeArticleSerializer,
    LedgerEntrySerializer, OrderSerializer, OrderItemSerializer, PaymentIntentSerializer, ProductSerializer, ReportSerializer,
    ResearchProjectSerializer, ResearchSourceSerializer,
)


class StaffWritePermission(BasePermission):
    """Authenticated users may read; only staff may mutate operational data."""
    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class InternalStaffWritePermission(BasePermission):
    """Internal records require authentication; mutations are staff-controlled."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return bool(request.user.is_staff)


class CatalogOwnerWritePermission(BasePermission):
    """Public catalog reads; only an active owner can mutate offerings."""

    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return is_authorized_chat_operator(request.user)


class OwnerTaskPermission(BasePermission):
    """Task inventories and controls are not staff-wide data."""

    def has_permission(self, request, view):
        return is_authorized_chat_operator(request.user)


def vs(model, serializer, permission=StaffWritePermission):
    return type(
        model.__name__ + "ViewSet",
        (viewsets.ModelViewSet,),
        {
            "queryset": model.objects.all(),
            "serializer_class": serializer,
            "permission_classes": [permission],
        },
    )


class OwnerScopedMixin:
    """Keep private research and commerce records visible only to their owner or staff."""

    owner_field = None

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return queryset
        return queryset.filter(**{self.owner_field: user})


class ProjectOwnerScopedMixin:
    """Scope project-linked research records to the owning user."""

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return queryset
        return queryset.filter(project__owner=user)


class ResearchProjectViewSet(OwnerScopedMixin, vs(ResearchProject, ResearchProjectSerializer, InternalStaffWritePermission)):
    owner_field = "owner"


class ResearchSourceViewSet(ProjectOwnerScopedMixin, vs(ResearchSource, ResearchSourceSerializer, InternalStaffWritePermission)):
    pass


class EvidenceViewSet(ProjectOwnerScopedMixin, vs(Evidence, EvidenceSerializer, InternalStaffWritePermission)):
    pass


class FindingViewSet(ProjectOwnerScopedMixin, vs(Finding, FindingSerializer, InternalStaffWritePermission)):
    pass


class ReportViewSet(ProjectOwnerScopedMixin, vs(Report, ReportSerializer, InternalStaffWritePermission)):
    pass


AgentViewSet = vs(Agent, AgentSerializer, InternalStaffWritePermission)
AgentCapabilityViewSet = vs(AgentCapability, AgentSerializer if False else AgentCapabilitySerializer, InternalStaffWritePermission)


class KnowledgeArticleViewSet(viewsets.ModelViewSet):
    """Published knowledge is public; publishing itself always requires owner approval."""

    queryset = KnowledgeArticle.objects.select_related("source_report__project").all()
    serializer_class = KnowledgeArticleSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return self.queryset
        if user.is_authenticated:
            return self.queryset.filter(
                models.Q(published=True) | models.Q(source_report__project__owner=user)
            ).distinct()
        return self.queryset.filter(published=True)

    def perform_create(self, serializer):
        serializer.save(published=False)

    def update(self, request, *args, **kwargs):
        article = self.get_object()
        if article.published:
            return Response(
                {"detail": "Published knowledge cannot be edited directly; create a new version."},
                status=status.HTTP_409_CONFLICT,
            )
        if "published" in request.data:
            return Response(
                {"detail": "Use the publish action; published is controlled by owner approval."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        article = self.get_object()
        if article.published:
            return Response(
                {"detail": "Knowledge article is already published."},
                status=status.HTTP_409_CONFLICT,
            )
        report = article.source_report
        if report is None or report.project is None:
            return Response(
                {"detail": "Knowledge article has no publishable research provenance."},
                status=status.HTTP_409_CONFLICT,
            )
        owner = report.project.owner
        if not owner:
            return Response(
                {"detail": "Knowledge article has no designated owner."},
                status=status.HTTP_409_CONFLICT,
            )
        pending = ApprovalRequest.objects.filter(
            action_type="publish",
            target_type="KnowledgeArticle",
            target_id=str(article.pk),
            status="pending",
            requested_by=owner,
        ).order_by("-created_at").first()
        if pending is None:
            pending = ApprovalRequest.objects.create(
                action_type="publish",
                target_type="KnowledgeArticle",
                target_id=str(article.pk),
                reason="Owner approval required before publishing knowledge.",
                risk="high",
                requested_by=owner,
            )
        return Response(
            {
                "status": "approval_required",
                "article": self.get_serializer(article).data,
                "approval": ApprovalRequestSerializer(pending).data,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("knowledge_article", "owner").all()
    serializer_class = ProductSerializer
    permission_classes = [CatalogOwnerWritePermission]

    def get_queryset(self):
        user = self.request.user
        if is_authorized_chat_operator(user):
            return self.queryset
        return self.queryset.filter(active=True, knowledge_article__published=True)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, active=False)

    def update(self, request, *args, **kwargs):
        product = self.get_object()
        if product.active:
            return Response(
                {"detail": "Active products are immutable; create a new approved version."},
                status=status.HTTP_409_CONFLICT,
            )
        allowed = frozenset({
            "title", "product_type", "price", "currency", "knowledge_article",
        })
        if not isinstance(request.data, dict) or not request.data or (
            set(request.data) - allowed
        ):
            return Response(
                {"detail": "Draft changes must use the allowlisted fields; owner and publication status are immutable."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if ApprovalRequest.objects.filter(
            target_type="Product", target_id=str(product.pk),
            action_type="activate_product", status="pending",
        ).exists():
            return Response(
                {"detail": "Reject the pending activation request before editing this draft."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Product deletion through the API is disabled; preserve commercial history."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        product = self.get_object()
        if product.active:
            return Response({"detail": "Product is already active."}, status=status.HTTP_409_CONFLICT)
        if product.owner_id != request.user.pk:
            return Response(
                {"detail": "Only the designated product owner can request activation."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if product.knowledge_article_id is None:
            return Response(
                {"detail": "Product must be mapped to a knowledge article before activation."},
                status=status.HTTP_409_CONFLICT,
            )
        if not product.knowledge_article.published:
            return Response(
                {"detail": "Mapped knowledge article must be published before activation."},
                status=status.HTTP_409_CONFLICT,
            )
        pending = ApprovalRequest.objects.filter(
            action_type="activate_product",
            target_type="Product",
            target_id=str(product.pk),
            status="pending",
            requested_by=product.owner,
        ).order_by("-created_at").first()
        if pending is None:
            pending = ApprovalRequest.objects.create(
                action_type="activate_product",
                target_type="Product",
                target_id=str(product.pk),
                reason="Owner approval required before activating a public product.",
                risk="high",
                requested_by=product.owner,
            )
        return Response(
            {"status": "approval_required", "product": self.get_serializer(product).data,
             "approval": ApprovalRequestSerializer(pending).data},
            status=status.HTTP_202_ACCEPTED,
        )


class OrderViewSet(OwnerScopedMixin, viewsets.ModelViewSet):
    queryset = Order.objects.prefetch_related("items__product").all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    owner_field = "customer"

    def get_queryset(self):
        if is_authorized_chat_operator(self.request.user):
            return self.queryset
        return self.queryset.filter(customer=self.request.user)

    def create(self, request, *args, **kwargs):
        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity", 1)
        if type(quantity) not in (int, str) or not re.fullmatch(
            r"[1-9][0-9]{0,2}", str(quantity),
        ):
            return Response({"detail": "quantity must be an integer from 1 to 100."}, status=status.HTTP_400_BAD_REQUEST)
        quantity = int(quantity)
        if not 1 <= quantity <= 100:
            return Response({"detail": "quantity must be an integer from 1 to 100."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                product = Product.objects.select_for_update().get(
                    pk=product_id, active=True, knowledge_article__published=True,
                )
            except (Product.DoesNotExist, TypeError, ValueError):
                return Response({"detail": "Active, published-knowledge-backed product not found."}, status=status.HTTP_404_NOT_FOUND)
            if product.price is None or not product.price.is_finite() or product.price <= 0:
                return Response({"detail": "Product has no valid positive price."}, status=status.HTTP_409_CONFLICT)
            total = product.price * quantity
            if total >= Decimal("1000000000000"):
                return Response(
                    {"detail": "Order total exceeds the database amount range."},
                    status=status.HTTP_409_CONFLICT,
                )
            order = Order.objects.create(
                customer=request.user,
                status="pending",
                total=total,
                currency=product.currency,
            )
            item = OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=product.price,
                currency=product.currency,
            )
        return Response(
            {
                "order": OrderSerializer(order).data,
                "item": OrderItemSerializer(item).data,
                "status": "created",
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Orders are immutable through direct update; use controlled lifecycle actions."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Order deletion is disabled to preserve reconciliation history."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class PaymentIntentViewSet(OwnerScopedMixin, viewsets.ReadOnlyModelViewSet):
    """Customer-owned intents; explicit product-owner approval, never billing."""
    queryset = PaymentIntent.objects.select_related("order__customer").all()
    serializer_class = PaymentIntentSerializer
    permission_classes = [IsAuthenticated]
    owner_field = "order__customer"

    def get_queryset(self):
        user = self.request.user
        if is_authorized_chat_operator(user):
            return self.queryset
        return self.queryset.filter(order__customer=user)

    @action(detail=False, methods=["post"], url_path="create")
    def create_intent(self, request):
        order_id = request.data.get("order_id")
        key = request.data.get("idempotency_key")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", key):
            return Response(
                {"detail": "A bounded idempotency_key (8-128 safe characters) is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if type(order_id) not in (str, int) or not str(order_id).isdigit():
            return Response({"detail": "A valid order_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().filter(
                    pk=order_id, customer=request.user,
                ).first()
                if order is None:
                    return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
                if order.status != "pending":
                    return Response({"detail": "Only pending orders can start payment."}, status=status.HTTP_409_CONFLICT)
                if order.total <= 0 or not order.total.is_finite():
                    return Response({"detail": "Invalid order amount."}, status=status.HTTP_409_CONFLICT)

                item = order.items.select_related("product__owner").first()
                owner = item.product.owner if item is not None else None
                if not is_authorized_chat_operator(owner):
                    return Response(
                        {"detail": "This product has no active designated payment approver."},
                        status=status.HTTP_409_CONFLICT,
                    )

                bound_key = PaymentIntent.objects.filter(idempotency_key=key).first()
                if bound_key is not None and bound_key.order_id != order.pk:
                    return Response(
                        {"detail": "Idempotency key belongs to another order."},
                        status=status.HTTP_409_CONFLICT,
                    )
                existing = PaymentIntent.objects.filter(order=order).first()
                if existing is not None:
                    if existing.idempotency_key != key:
                        return Response(
                            {"detail": "An existing payment intent uses a different key."},
                            status=status.HTTP_409_CONFLICT,
                        )
                    return Response(
                        {"status": "existing", "payment_intent": self.get_serializer(existing).data},
                        status=status.HTTP_200_OK,
                    )

                intent = PaymentIntent.objects.create(
                    order=order,
                    amount=order.total,
                    currency=order.currency,
                    idempotency_key=key,
                    status="awaiting_approval",
                    provider="not_configured",
                )
                approval = ApprovalRequest.objects.create(
                    action_type="payment",
                    target_type="PaymentIntent",
                    target_id=str(intent.pk),
                    reason="Exact designated product owner approval required before any external payment.",
                    risk="critical",
                    requested_by=owner,
                )
        except (IntegrityError, ValueError, TypeError):
            return Response(
                {"detail": "Concurrent or invalid payment intent; inspect existing order state."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            {
                "status": "approval_required",
                "payment_intent": self.get_serializer(intent).data,
                "approval": ApprovalRequestSerializer(approval).data,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class PaymentWebhookViewSet(viewsets.ViewSet):
    """Strictly configured provider callback; not independent cash settlement."""
    permission_classes = [AllowAny]

    def create(self, request):
        provider = str(request.headers.get("X-Payment-Provider", ""))
        event_id = str(request.headers.get("X-Payment-Event-Id", ""))
        signature = str(request.headers.get("X-Payment-Signature", ""))
        configured_provider = str(getattr(settings, "PAYMENT_WEBHOOK_PROVIDER", "") or "")
        secret = str(getattr(settings, "PAYMENT_WEBHOOK_SECRET", "") or "")
        # No generic shared-secret provider impersonation, and never accept
        # the sentinel provider on an unconfigured deployment.
        if (not configured_provider or configured_provider == "not_configured"
                or provider != configured_provider or not secret):
            return Response({"detail": "Payment provider is not explicitly configured."},
                            status=status.HTTP_401_UNAUTHORIZED)
        if (not re.fullmatch(r"[A-Za-z0-9._:-]{1,50}", provider)
                or not re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", event_id)
                or not re.fullmatch(r"[0-9a-f]{64}", signature)):
            return Response({"detail": "Invalid signed event envelope."},
                            status=status.HTTP_401_UNAUTHORIZED)

        raw = request.body
        if len(raw) > 32768:
            return Response({"detail": "Webhook body exceeds the configured limit."},
                            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return Response({"detail": "Invalid webhook signature."},
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response({"detail": "Webhook payload must be valid JSON."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(payload, dict):
            return Response({"detail": "Webhook payload must be a JSON object."},
                            status=status.HTTP_400_BAD_REQUEST)

        event_type = payload.get("event_type")
        intent_id = payload.get("payment_intent_id")
        provider_reference = payload.get("provider_reference")
        if event_type not in ("payment.succeeded", "payment.failed"):
            return Response({"detail": "Unsupported payment event type."},
                            status=status.HTTP_400_BAD_REQUEST)
        if (type(intent_id) not in (int, str) or not str(intent_id).isdigit()
                or not isinstance(provider_reference, str)
                or not 1 <= len(provider_reference) <= 200
                or provider_reference != provider_reference.strip()):
            return Response({"detail": "Valid intent ID and provider reference are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        payload_hash = hashlib.sha256(raw).hexdigest()
        with transaction.atomic():
            existing = PaymentWebhookEvent.objects.select_for_update().filter(
                provider=provider, event_id=event_id,
            ).first()
            if existing:
                if existing.payload_hash != payload_hash:
                    return Response(
                        {"detail": "Webhook event ID reused with different content."},
                        status=status.HTTP_409_CONFLICT,
                    )
                return Response({"status": existing.status, "event_id": event_id},
                                status=status.HTTP_200_OK)

            intent = PaymentIntent.objects.select_for_update().filter(
                pk=intent_id, provider=provider,
            ).first()
            if intent is None:
                return Response({"detail": "Payment intent not found for configured provider."},
                                status=status.HTTP_404_NOT_FOUND)
            order = Order.objects.select_for_update().get(pk=intent.order_id)
            event = PaymentWebhookEvent.objects.create(
                provider=provider,
                event_id=event_id,
                event_type=event_type,
                payment_intent=intent,
                payload_hash=payload_hash,
                status="received",
            )

            # Both success and failure may only transition a pending order
            # whose intent was specifically approved for this provider.
            settleable = (
                intent.status in ("ready_for_gateway", "gateway_pending")
                and order.status == "pending"
                and intent.amount == order.total
                and intent.currency == order.currency
                and intent.amount.is_finite() and intent.amount > 0
                and not PaymentIntent.objects.filter(
                    provider=provider, provider_reference=provider_reference,
                ).exclude(pk=intent.pk).exists()
            )
            if event_type == "payment.succeeded" and settleable:
                amount = payload.get("amount")
                currency = payload.get("currency")
                try:
                    amount_valid = (
                        type(amount) in (str, int)
                        and Decimal(str(amount)).is_finite()
                        and Decimal(str(amount)) == intent.amount
                    )
                except (InvalidOperation, TypeError, ValueError):
                    amount_valid = False
                if not amount_valid or currency != intent.currency:
                    settleable = False
                if LedgerEntry.objects.filter(
                    payment_intent=intent, entry_type="payment",
                ).exists():
                    settleable = False

            if not settleable:
                event.status = "rejected"
                event.error = "Payment event is inconsistent with approved pending order."
            elif event_type == "payment.succeeded":
                intent.status = "succeeded"
                intent.provider_reference = provider_reference
                intent.save(update_fields=["status", "provider_reference", "updated_at"])
                order.status = "paid"
                order.save(update_fields=["status", "updated_at"])
                LedgerEntry.objects.create(
                    reference="payment:" + hashlib.sha256(
                        f"{provider}:{event_id}".encode("utf-8")
                    ).hexdigest(),
                    order=order,
                    payment_intent=intent,
                    entry_type="payment",
                    amount=intent.amount,
                    currency=intent.currency,
                    metadata={"provider": provider, "event_id": event_id},
                )
                event.status = "processed"
            else:
                # A late "failed" event must never demote succeeded intent or
                # a paid order. The settleable guard enforces this.
                intent.status = "failed"
                intent.provider_reference = provider_reference
                intent.save(update_fields=["status", "provider_reference", "updated_at"])
                event.status = "processed"

            event.processed_at = timezone.now()
            event.save(update_fields=["status", "error", "processed_at", "updated_at"])
            AuditLog.objects.create(
                actor_type="payment_provider",
                actor_id=provider,
                action="payment_webhook_processed",
                target_type="PaymentIntent",
                target_id=str(intent.pk),
                after_state={
                    "event_id": event_id, "event_type": event_type,
                    "status": event.status, "settlement_independently_attested": False,
                },
                # AuditLog.trace_id is max_length=100. Do not concatenate
                # the untrusted 200-character event ID into it.
                trace_id=f"payment-webhook-{payload_hash[:40]}",
            )

        return Response({"status": event.status, "event_id": event_id},
                        status=status.HTTP_200_OK)


class AgentTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """Owner-scoped task inventory; master execution lives in WorkerRunner."""
    queryset = AgentTask.objects.all()
    serializer_class = AgentTaskSerializer
    permission_classes = [OwnerTaskPermission]

    def get_queryset(self):
        user = self.request.user
        if not is_authorized_chat_operator(user):
            return AgentTask.objects.none()
        return AgentTask.objects.select_related("agent", "project").filter(
            models.Q(project__owner=user)
            | models.Q(project__isnull=True, agent__code=BOT_CODE)
        )

    def _master_api_lifecycle_denial(self):
        """Browser/user API cannot synthesize a master execution receipt."""
        task = self.get_object()
        if task.agent.code in EXECUTOR_RUNTIME_CODES:
            return Response(
                {"detail": "MASTER_LIFECYCLE_VIA_HTTP_FORBIDDEN_USE_WORKER_RUNNER"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    @action(detail=True, methods=["get"], url_path="reconciliation")
    def reconciliation(self, request, pk=None):
        """Owner-only local audit synopsis; never a retrigger endpoint."""
        if not is_authorized_chat_operator(request.user):
            return Response(
                {"detail": "Active owner permission required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        task = self.get_object()
        if task.project_id and task.project.owner_id != request.user.pk:
            return Response(
                {"detail": "Task belongs to another project owner."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            report = build_reconciliation_dossier(task, actor=request.user)
        except PermissionError:
            return Response(
                {"detail": "Exact project owner required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(report)

    @action(detail=True, methods=["post"], url_path="record-reconciliation")
    def record_reconciliation(self, request, pk=None):
        """Append an owner assertion only; never release or retry the task."""
        if not is_authorized_chat_operator(request.user):
            return Response(
                {"detail": "Active owner permission required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            task = self.get_object()
            result = record_reconciliation_observation(
                task.pk,
                actor=request.user,
                evidence_sha256=request.data.get("evidence_sha256"),
                source_kind=request.data.get("source_kind"),
                disposition=request.data.get("disposition"),
            )
        except AgentTask.DoesNotExist:
            return Response(
                {"detail": "Task not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PermissionError:
            return Response(
                {"detail": "Project owner permission required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="claim")
    def claim(self, request, pk=None):
        denied = self._master_api_lifecycle_denial()
        if denied is not None:
            return denied
        try:
            task = TaskRuntime().claim(pk)
        except AgentTask.DoesNotExist:
            return Response({"detail": "Task not found."}, status=status.HTTP_404_NOT_FOUND)
        except (TaskExecutionError, ImproperlyConfigured) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AgentTaskSerializer(task).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        denied = self._master_api_lifecycle_denial()
        if denied is not None:
            return denied
        output_data = request.data.get("output_data") or {}
        if not isinstance(output_data, dict):
            return Response({"detail": "output_data must be an object."}, status=status.HTTP_400_BAD_REQUEST)
        cost = request.data.get("cost", 0)
        try:
            task = TaskRuntime().complete(pk, output_data=output_data, cost=cost, execution_id=str(request.data.get("execution_id", "")).strip())
        except AgentTask.DoesNotExist:
            return Response({"detail": "Task not found."}, status=status.HTTP_404_NOT_FOUND)
        except (TaskExecutionError, ValueError, TypeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AgentTaskSerializer(task).data)

    @action(detail=True, methods=["post"], url_path="heartbeat")
    def heartbeat(self, request, pk=None):
        denied = self._master_api_lifecycle_denial()
        if denied is not None:
            return denied
        execution_id = str(request.data.get("execution_id", "")).strip()
        if not execution_id:
            return Response({"detail": "execution_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            task = TaskRuntime().heartbeat(pk, execution_id=execution_id)
        except AgentTask.DoesNotExist:
            return Response({"detail": "Task not found."}, status=status.HTTP_404_NOT_FOUND)
        except TaskExecutionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AgentTaskSerializer(task).data)

    @action(detail=True, methods=["post"], url_path="recover-stale")
    def recover_stale(self, request, pk=None):
        denied = self._master_api_lifecycle_denial()
        if denied is not None:
            return denied
        stale_after = request.data.get("stale_after_seconds", 900)
        try:
            task = TaskRuntime().recover_stale(pk, stale_after_seconds=stale_after)
        except AgentTask.DoesNotExist:
            return Response({"detail": "Task not found."}, status=status.HTTP_404_NOT_FOUND)
        except TaskExecutionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AgentTaskSerializer(task).data)

    @action(detail=True, methods=["post"], url_path="fail")
    def fail(self, request, pk=None):
        denied = self._master_api_lifecycle_denial()
        if denied is not None:
            return denied
        error = str(request.data.get("error", "")).strip()
        if not error:
            return Response({"detail": "error is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            task = TaskRuntime().fail(pk, error, execution_id=str(request.data.get("execution_id", "")).strip())
        except AgentTask.DoesNotExist:
            return Response({"detail": "Task not found."}, status=status.HTTP_404_NOT_FOUND)
        except TaskExecutionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AgentTaskSerializer(task).data)

class ApprovalRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """Owner approvals are read-only except for the controlled decision action."""
    queryset = ApprovalRequest.objects.select_related("requested_by").all()
    serializer_class = ApprovalRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return self.queryset
        return self.queryset.filter(requested_by=user)

    @action(detail=True, methods=["post"], url_path="decide")
    def decide(self, request, pk=None):
        approval = self.get_object()
        if approval.target_type == "ChatOperation" and not is_authorized_chat_operator(request.user):
            return Response(
                {"detail": "Only an active superuser can approve chat operations."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if approval.requested_by_id != request.user.pk:
            return Response(
                {"detail": "Only the designated owner can decide this approval."},
                status=status.HTTP_403_FORBIDDEN,
            )

        approved = request.data.get("approved")
        if not isinstance(approved, bool):
            return Response(
                {"detail": "approved must be a boolean."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        note = str(request.data.get("note", ""))[:5000]
        try:
            approval = ApprovalService().decide(
                approval_id=approval.pk,
                approved=approved,
                actor_id=request.user.pk,
                actor_type="owner",
                note=note,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(approval).data)


    @action(detail=True, methods=["post"], url_path="execute-chat")
    def execute_chat(self, request, pk=None):
        """Separate explicit execution after an independently recorded decision."""
        approval = self.get_object()
        if approval.target_type != "ChatOperation":
            return Response({"detail": "Not a chat operation."}, status=status.HTTP_409_CONFLICT)
        if (not is_authorized_chat_operator(request.user)
                or approval.requested_by_id != request.user.pk):
            return Response({"detail": "Owner authorization required."},
                            status=status.HTTP_403_FORBIDDEN)
        if approval.status != "approved":
            return Response({"detail": "Explicit approval required before execution."},
                            status=status.HTTP_409_CONFLICT)
        from .operation_executor import execute_approved_chat_operation
        try:
            result = execute_approved_chat_operation(approval)
        except (ValueError, PermissionError, RuntimeError, KeyError, TypeError):
            return Response({"detail": "Execution blocked or requires reconciliation."},
                            status=status.HTTP_409_CONFLICT)
        return Response(result)

class MasterAgentChatViewSet(viewsets.ModelViewSet):
    queryset = ChatSession.objects.all()
    serializer_class = ChatSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        session = ChatSession.objects.create(
            user=request.user,
            title=str(request.data.get("title", ""))[:300],
        )
        message = str(request.data.get("message", "")).strip()
        if message:
            try:
                from .chat_runtime import MasterAgentChat
                reply = MasterAgentChat().respond(session, message)
            except Exception as exc:
                return Response(
                    {"detail": "Master Agent chat is temporarily unavailable."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response({
                "session": ChatSessionSerializer(session).data,
                "reply": reply,
                "messages": ChatMessageSerializer(
                    session.messages.order_by("created_at"), many=True
                ).data,
            }, status=status.HTTP_201_CREATED)
        return Response({"session": ChatSessionSerializer(session).data}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="plan", permission_classes=[InternalStaffWritePermission])
    def plan(self, request, *args, **kwargs):
        # Planning is a durable operation: staff status alone is insufficient
        # to schedule tasks or nominate their authorizing owner.
        if not is_authorized_chat_operator(request.user):
            return Response(
                {"detail": "Only the active owner can plan master tasks."},
                status=status.HTTP_403_FORBIDDEN,
            )
        project_id = request.data.get("project_id")
        action_type = str(request.data.get("action_type", "")).strip()
        payload = request.data.get("payload") or {}
        risk = str(request.data.get("risk", "low")).strip() or "low"
        if not project_id or not action_type:
            return Response({"detail": "project_id and action_type are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project = ResearchProject.objects.get(pk=project_id)
            task = MasterAgent().plan(
                project, action_type, payload,
                risk=risk, requester=request.user,
            )
        except ResearchProject.DoesNotExist:
            return Response({"detail": "Research project not found."}, status=status.HTTP_404_NOT_FOUND)
        except (RuntimeError, ValueError, PermissionError, ImproperlyConfigured) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AgentTaskSerializer(task).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="messages")
    def message(self, request, pk=None):
        session = self.get_object()
        text = str(request.data.get("message", "")).strip()
        if not text:
            return Response({"detail": "message is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from .chat_runtime import MasterAgentChat
            reply = MasterAgentChat().respond(session, text)
        except Exception as exc:
            return Response(
                {"detail": "Master Agent chat is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({
            "reply": reply,
            "messages": ChatMessageSerializer(
                session.messages.order_by("created_at"), many=True
            ).data,
        })
