from django.urls import path
from .views import dashboard, overview_api
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
from .mpw_monitor_views import dashboard as mpw_monitor, telemetry_api as mpw_monitor_api
from .mpw_operations import desk as mpw_operations
from .mpw_two_books_panel import dashboard as mpw_two_books_dashboard
from .business_review_views import business_review

urlpatterns = [
    path("", dashboard, name="command_center_dashboard"),
    path("mpw-agents/", mpw_monitor, name="mpw_agent_monitor"),
    path("mpw-operations/", mpw_operations, name="mpw_operations"),
    path("mpw-two-books/", mpw_two_books_dashboard, name="mpw_two_books_dashboard"),
    path("api/mpw-agents/", mpw_monitor_api, name="mpw_agent_monitor_api"),
    path("api/overview/", overview_api, name="command_center_overview_api"),
    path("api/business-operating/", business_review, name="command_center_business_operating_api"),
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
