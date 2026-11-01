"""URLConf mounted by CloudLinux at /company/office/ only."""
from django.urls import include, path

urlpatterns = [
    path("messages/", include("company_messaging.urls")),
    path("marketing/", include("company_marketing.urls")),
    path("", include("enterprise_portal.urls")),
]
