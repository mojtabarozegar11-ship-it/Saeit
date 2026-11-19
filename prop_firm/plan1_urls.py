from django.urls import path

from .plan1_views import start_plan1_invoice

app_name = "mojprop_plan1"

urlpatterns = [
    path("start/", start_plan1_invoice, name="start"),
]
