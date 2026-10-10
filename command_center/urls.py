from django.urls import path
from .views import dashboard, overview_api

urlpatterns = [
    path("", dashboard, name="command_center_dashboard"),
    path("api/overview/", overview_api, name="command_center_overview_api"),
]
