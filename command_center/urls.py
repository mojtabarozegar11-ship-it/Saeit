from django.urls import path
from .views import dashboard, overview_api
from .agent_views import metrics

urlpatterns = [
    path("", dashboard, name="command_center_dashboard"),
    path("api/overview/", overview_api, name="command_center_overview_api"),
    path("api/agents/", metrics, name="command_center_agent_metrics_api"),
]
