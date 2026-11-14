from django.urls import include, path
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
from .operations import operations_summary
from .management_report import management_report
from .controls import controls_summary
from .integrated_views import integrated_dashboard
from .integrated_ledger_api import integrated_ledger_api
from .commerce_funnel import commerce_funnel_api
from .revenue_evidence import revenue_evidence_api
from .fulfillment_preflight import fulfillment_preflight_api
from .company_sales_pipeline import company_sales_pipeline_api
from .company_quote_desk import sales_cases, sales_case_detail, sales_case_action

urlpatterns = [
    path("", dashboard, name="command_center_dashboard"),
    path("accounting/", include("accounting.urls")),
    path("mpw-agents/", mpw_monitor, name="mpw_agent_monitor"),
    path("mpw-operations/", mpw_operations, name="mpw_operations"),
    path("mpw-two-books/", mpw_two_books_dashboard, name="mpw_two_books_dashboard"),
    path("api/mpw-agents/", mpw_monitor_api, name="mpw_agent_monitor_api"),
    path("api/overview/", overview_api, name="command_center_overview_api"),
    path("api/management-report/", management_report, name="command_center_management_report_api"),
    path("api/operations/summary/", operations_summary, name="command_center_operations_summary_api"),
    path("api/controls/summary/", controls_summary, name="command_center_controls_summary_api"),
    path("integrated/", integrated_dashboard, name="command_center_integrated_dashboard"),
    path("api/integrated-ledger/", integrated_ledger_api, name="command_center_integrated_ledger_api"),
    path("api/commerce-funnel/", commerce_funnel_api, name="command_center_commerce_funnel_api"),
    path("api/bot/revenue-evidence/", revenue_evidence_api, name="mojtaba_bot_revenue_evidence_api"),
    path("api/bot/fulfillment-preflight/", fulfillment_preflight_api, name="mojtaba_bot_fulfillment_preflight_api"),
    path("api/bot/sales-pipeline/", company_sales_pipeline_api, name="mojtaba_bot_sales_pipeline_api"),
    path("sales-cases/", sales_cases, name="mojtaba_company_sales_cases"),
    path("sales-cases/<int:case_id>/", sales_case_detail, name="mojtaba_company_case_detail"),
    path("sales-cases/<int:case_id>/<str:operation>/", sales_case_action, name="mojtaba_company_case_action"),
    path("api/agents/", metrics, name="command_center_agent_metrics_api"),
    path("api/bot/modules/", directory, name="command_center_unified_bot_modules_api"),
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
