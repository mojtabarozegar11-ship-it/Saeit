from django.urls import path
from . import views
from . import financial_reporting as income

app_name = "ecosystem_hub"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("modules/", views.modules, name="modules"),
    path("group/", views.group_overview, name="group_overview"),
    path("finance/income/", income.income_report, name="income_report"),
    path("finance/income.csv", income.income_csv, name="income_csv"),
    path("production/", views.production, name="production"),
    path("production/cost/<int:pk>/", views.production_cost, name="production_cost"),
    path("production/materials/<int:pk>/", views.production_material_plan, name="material_plan"),
    path("production/materials/<int:pk>/draft-procurement/", views.create_procurement_drafts, name="create_procurement_drafts"),
    path("oversight/", views.oversight, name="oversight"),
    path("assistants/", views.assistants, name="assistants"),
    path("assistants/<slug:code>/run/", views.run_assistant, name="run_assistant"),
    path("reports/<int:pk>/", views.report, name="report"),
    path("reports/<int:pk>/request-review/", views.request_review, name="request_review"),
]
