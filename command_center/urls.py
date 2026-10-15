from django.urls import path
from .views import dashboard, overview_api
from .workflow import stages
from .agent_views import metrics
from .agent_directory import directory
from .agent_proposals import propose
from .approval_queue import pending
from .content_stats import stats
from .editorial_queue import queue
from .editorial_detail import detail
from .media_album import album
from .agent_media_catalog import search as media_search
from .story_image_suggestions import suggestions as story_images

urlpatterns = [
    path("", dashboard, name="command_center_dashboard"),
    path("api/overview/", overview_api, name="command_center_overview_api"),
    path("api/workflow/", stages, name="command_center_workflow_api"),
    path("api/agents/", metrics, name="command_center_agent_metrics_api"),
    path("api/agents/directory/", directory, name="command_center_agent_directory_api"),
    path("api/agents/proposals/", propose, name="command_center_agent_proposals_api"),
    path("api/approvals/pending/", pending, name="command_center_pending_approvals_api"),
    path("api/content/stats/", stats, name="command_center_content_stats_api"),
    path("api/content/queue/", queue, name="command_center_editorial_queue_api"),
    path("api/content/stories/<int:story_id>/", detail, name="command_center_editorial_detail_api"),
    path("api/content/album/", album, name="command_center_media_album_api"),
    path("api/content/album/search/", media_search, name="command_center_media_search_api"),
    path("api/content/stories/<int:story_id>/images/", story_images, name="command_center_story_image_suggestions_api"),
]
