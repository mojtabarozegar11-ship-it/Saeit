
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from core.views import home, platform_page
from core.commerce_views import store_home, auctions_home
from core.seo_views import site_search, robots_txt, sitemap_xml
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
    path("search/", site_search, name="site_search"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),
    path("store/", store_home, name="store"),
    path("auctions/", auctions_home, name="auctions"),
    path("company/", lambda request: platform_page(request, "company"), name="company"),
    path("company/<slug:slug>/", lambda request, slug: platform_page(request, "company"), name="company_detail"),
    path("about/", RedirectView.as_view(pattern_name="company", permanent=True), name="about"),
    path("contact/", RedirectView.as_view(pattern_name="company", permanent=True), name="contact"),
    path("weather/", weather, name="weather"),
    path("academy/", academy, name="academy"),
    path("services/", services, name="services"),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
]

from core.newsletter_views import newsletter_home, newsletter_archive, newsletter_detail
urlpatterns += [path("newsletter/", newsletter_home, name="newsletter"), path("newsletter/archive/", newsletter_archive, name="newsletter_archive"), path("newsletter/<slug:slug>/", newsletter_detail, name="newsletter_detail")]

from core.blog_views import blog_home, blog_page
urlpatterns += [path("blog/", blog_home, name="blog"), path("blog/<slug:slug>/", blog_page, name="blog_page")]
