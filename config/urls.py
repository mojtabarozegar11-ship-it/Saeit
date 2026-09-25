

from django.contrib import admin
from django.urls import include, path

from core.views import home, platform_page
from core.weather_views import weather
from core.academy_views import academy
from core.services_views import services

urlpatterns = [
    path("", home, name="home"),
    path("agriculture/", lambda request: platform_page(request, "agriculture"), name="agriculture"),
    path("industry/", lambda request: platform_page(request, "industry"), name="industry"),
    path("research/", lambda request: platform_page(request, "research"), name="research"),
    path("knowledge/", lambda request: platform_page(request, "knowledge"), name="knowledge"),
    path("market/", lambda request: platform_page(request, "market"), name="market"),
    path("agents/", lambda request: platform_page(request, "agents"), name="agents"),
    path("about/", lambda request: platform_page(request, "about"), name="about"),
    path("contact/", lambda request: platform_page(request, "contact"), name="contact"),
    path("weather/", weather, name="weather"),
    path("academy/", academy, name="academy"),
    path("services/", services, name="services"),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
]
