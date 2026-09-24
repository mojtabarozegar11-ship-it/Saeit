from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .approval import ApprovalService
from .models import (
    Agent,
    AgentTask,
    ApprovalRequest,
    Evidence,
    Finding,
    KnowledgeArticle,
    Order,
    Product,
    Report,
    ResearchProject,
    ResearchSource,
)
from .serializers import (
    AgentSerializer,
    AgentTaskSerializer,
    ApprovalRequestSerializer,
    EvidenceSerializer,
    FindingSerializer,
    KnowledgeArticleSerializer,
    OrderSerializer,
    ProductSerializer,
    ReportSerializer,
    ResearchProjectSerializer,
    ResearchSourceSerializer,
)


def vs(model, serializer):
    return type(
        model.__name__ + "ViewSet",
        (viewsets.ModelViewSet,),
        {
            "queryset": model.objects.all(),
            "serializer_class": serializer,
        },
    )


ResearchProjectViewSet = vs(ResearchProject, ResearchProjectSerializer)
ResearchSourceViewSet = vs(ResearchSource, ResearchSourceSerializer)
EvidenceViewSet = vs(Evidence, EvidenceSerializer)
FindingViewSet = vs(Finding, FindingSerializer)
ReportViewSet = vs(Report, ReportSerializer)
AgentViewSet = vs(Agent, AgentSerializer)
AgentTaskViewSet = vs(AgentTask, AgentTaskSerializer)
KnowledgeArticleViewSet = vs(KnowledgeArticle, KnowledgeArticleSerializer)
ProductViewSet = vs(Product, ProductSerializer)
OrderViewSet = vs(Order, OrderSerializer)


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
        approval = ApprovalService().decide(
            approval_id=approval.pk,
            approved=approved,
            actor_id=request.user.pk,
            note=note,
        )
        return Response(self.get_serializer(approval).data)
