from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .approval import ApprovalService
from .chat_runtime import MasterAgentChat
from .task_runtime import TaskExecutionError, TaskRuntime


from .orchestrator import MasterAgent
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


ResearchProjectViewSet = vs(ResearchProject, ResearchProjectSerializer, InternalStaffWritePermission)
ResearchSourceViewSet = vs(ResearchSource, ResearchSourceSerializer, InternalStaffWritePermission)
EvidenceViewSet = vs(Evidence, EvidenceSerializer, InternalStaffWritePermission)
FindingViewSet = vs(Finding, FindingSerializer, InternalStaffWritePermission)
ReportViewSet = vs(Report, ReportSerializer, InternalStaffWritePermission)
AgentViewSet = vs(Agent, AgentSerializer, InternalStaffWritePermission)
AgentCapabilityViewSet = vs(AgentCapability, AgentCapabilitySerializer, InternalStaffWritePermission)
KnowledgeArticleViewSet = vs(KnowledgeArticle, KnowledgeArticleSerializer)
ProductViewSet = vs(Product, ProductSerializer)
OrderViewSet = vs(Order, OrderSerializer, InternalStaffWritePermission)


class AgentTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """Tasks are created only through Master Agent planning, never by direct CRUD."""
    queryset = AgentTask.objects.all()
    serializer_class = AgentTaskSerializer
    permission_classes = [InternalStaffWritePermission]

    @action(detail=True, methods=["post"], url_path="claim")
    def claim(self, request, pk=None):
        try:
            task = TaskRuntime().claim(pk)
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
                    {"detail": "Master Agent chat is temporarily unavailable.", "error": str(exc)[:500]},
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
                {"detail": "Master Agent chat is temporarily unavailable.", "error": str(exc)[:500]},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({
            "reply": reply,
            "messages": ChatMessageSerializer(
                session.messages.order_by("created_at"), many=True
            ).data,
        })
