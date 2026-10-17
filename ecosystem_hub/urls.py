from django.urls import path
from . import views

app_name = "ecosystem_hub"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("modules/", views.modules, name="modules"),
    path("production/", views.production, name="production"),
    path("oversight/", views.oversight, name="oversight"),
    path("assistants/", views.assistants, name="assistants"),
    path("assistants/<slug:code>/run/", views.run_assistant, name="run_assistant"),
    path("reports/<int:pk>/", views.report, name="report"),
]
