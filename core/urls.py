from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api import (
    AgentCapabilityViewSet,
    MasterAgentChatViewSet,
    AgentTaskViewSet,
    AgentViewSet,
    ApprovalRequestViewSet,
    EvidenceViewSet,
    FindingViewSet,
    KnowledgeArticleViewSet,
    OrderViewSet,
    ProductViewSet,
    ReportViewSet,
    ResearchProjectViewSet,
    ResearchSourceViewSet,
)
from .views import HealthView

router = DefaultRouter()
router.register("projects", ResearchProjectViewSet, basename="research-project")
router.register("sources", ResearchSourceViewSet, basename="research-source")
router.register("evidence", EvidenceViewSet, basename="evidence")
router.register("findings", FindingViewSet, basename="finding")
router.register("reports", ReportViewSet, basename="report")
router.register("agents", AgentViewSet, basename="agent")
router.register("agent-capabilities", AgentCapabilityViewSet, basename="agent-capability")
router.register("tasks", AgentTaskViewSet, basename="agent-task")
router.register("approvals", ApprovalRequestViewSet, basename="approval-request")
router.register("master-chat", MasterAgentChatViewSet, basename="master-agent-chat")
router.register("knowledge", KnowledgeArticleViewSet, basename="knowledge-article")
router.register("products", ProductViewSet, basename="product")
router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("health/", HealthView.as_view()),
    path("", include(router.urls)),
]
