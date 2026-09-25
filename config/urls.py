[Reading 20 lines from start (total: 20 lines, 0 remaining)]

from django.contrib import admin
from django.urls import include, path

from core.views import home, platform_page
from core.weather_views import weather

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
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
]

[executed on device: zohal.pws-dns.net (457d9cac-c176-4c0a-a847-08fb0f2007dc)]