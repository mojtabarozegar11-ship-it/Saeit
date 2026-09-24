from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .approval import ApprovalService
from .models import (
    Agent, AgentTask, ApprovalRequest, Evidence, Finding,
    KnowledgeArticle, Order, Product, Report, ResearchProject, ResearchSource,
)
from .serializers import (
    AgentSerializer, AgentTaskSerializer, ApprovalRequestSerializer,
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
AgentTaskViewSet = vs(AgentTask, AgentTaskSerializer, InternalStaffWritePermission)
KnowledgeArticleViewSet = vs(KnowledgeArticle, KnowledgeArticleSerializer)
ProductViewSet = vs(Product, ProductSerializer)
OrderViewSet = vs(Order, OrderSerializer, InternalStaffWritePermission)


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
        if approval.requested_by_id != request.user.pk and not request.user.is_staff:
            return Response(
                {"detail": "Only the owner or an authorized staff user can decide this approval."},
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
                note=note,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(approval).data)
