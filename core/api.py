from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .approval import ApprovalService
from .chat_runtime import MasterAgentChat
from .task_runtime import TaskExecutionError, TaskRuntime


from .orchestrator import MasterAgent
from django.db import models

from .models import (
    Agent, AgentCapability, AgentTask, ApprovalRequest, ChatMessage, ChatSession, Evidence, Finding,
    KnowledgeArticle, Order, Product, Report, ResearchProject, ResearchSource,
)
from .serializers import (
    AgentCapabilitySerializer, AgentSerializer, AgentTaskSerializer, ApprovalRequestSerializer, ChatMessageSerializer, ChatSessionSerializer,
    EvidenceSerializer, FindingSerializer, KnowledgeArticleSerializer,
    OrderSerializer, ProductSerializer, ReportSerializer,
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
    permission_classes = [StaffWritePermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return self.queryset
        return self.queryset.filter(active=True, knowledge_article__published=True)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, active=False)

    def update(self, request, *args, **kwargs):
        product = self.get_object()
        if "active" in request.data:
            return Response(
                {"detail": "Use the activate action; activation requires owner approval."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

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


class OrderViewSet(OwnerScopedMixin, vs(Order, OrderSerializer, InternalStaffWritePermission)):
    owner_field = "customer"


class AgentTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """Tasks are created only through Master Agent planning, never by direct CRUD."""
    queryset = AgentTask.objects.all()
    serializer_class = AgentTaskSerializer
    permission_classes = [InternalStaffWritePermission]

    @action(detail=True, methods=["post"], url_path="claim")
    def claim(self, request, pk=None):
        try:
            task = TaskRuntime().claim(pk)
        except AgentTask.DoesNotExist:
            return Response({"detail": "Task not found."}, status=status.HTTP_404_NOT_FOUND)
        except TaskExecutionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AgentTaskSerializer(task).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
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
        project_id = request.data.get("project_id")
        action_type = str(request.data.get("action_type", "")).strip()
        payload = request.data.get("payload") or {}
        risk = str(request.data.get("risk", "low")).strip() or "low"
        if not project_id or not action_type:
            return Response({"detail": "project_id and action_type are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project = ResearchProject.objects.get(pk=project_id)
            task = MasterAgent().plan(project, action_type, payload, risk=risk)
        except ResearchProject.DoesNotExist:
            return Response({"detail": "Research project not found."}, status=status.HTTP_404_NOT_FOUND)
        except (RuntimeError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AgentTaskSerializer(task).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="messages")
    def message(self, request, pk=None):
        session = self.get_object()
        text = str(request.data.get("message", "")).strip()
        if not text:
            return Response({"detail": "message is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
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
