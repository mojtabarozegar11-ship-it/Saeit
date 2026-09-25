[Reading 34 lines from start (total: 34 lines, 0 remaining)]

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api import (
    AgentCapabilityViewSet, MasterAgentChatViewSet, AgentTaskViewSet, AgentViewSet,
    ApprovalRequestViewSet, EvidenceViewSet, FindingViewSet, KnowledgeArticleViewSet,
    OrderViewSet, PaymentIntentViewSet, PaymentWebhookViewSet, ProductViewSet,
    ReportViewSet, ResearchProjectViewSet, ResearchSourceViewSet,
)
from .views import HealthView
from .weather_views import weather_api

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
router.register("payments", PaymentIntentViewSet, basename="payment-intent")
router.register("payment-webhooks", PaymentWebhookViewSet, basename="payment-webhook")

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("weather/", weather_api, name="weather"),
    path("", include(router.urls)),
]

[executed on device: zohal.pws-dns.net (457d9cac-c176-4c0a-a847-08fb0f2007dc)]