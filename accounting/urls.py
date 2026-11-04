from django.urls import path
from .views import dashboard, summary_api

urlpatterns = [
    path("", dashboard, name="accounting_dashboard"),
    path("api/summary/", summary_api, name="accounting_summary_api"),
]
