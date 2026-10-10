from django.urls import path
from .views import dashboard, overview_api
from .agent_views import metrics
from .agent_directory import directory
from .agent_proposals import propose
from .approval_queue import pending
from .content_stats import stats

urlpatterns = [
    path("", dashboard, name="command_center_dashboard"),
    path("api/overview/", overview_api, name="command_center_overview_api"),
    path("api/agents/", metrics, name="command_center_agent_metrics_api"),
    path("api/agents/directory/", directory, name="command_center_agent_directory_api"),
    path("api/agents/proposals/", propose, name="command_center_agent_proposals_api"),
    path("api/approvals/pending/", pending, name="command_center_pending_approvals_api"),
    path("api/content/stats/", stats, name="command_center_content_stats_api"),
]
