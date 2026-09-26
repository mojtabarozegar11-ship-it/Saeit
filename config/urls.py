
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from core.views import home, platform_page
from core.commerce_views import store_home, auctions_home
from core.seo_views import site_search, robots_txt, sitemap_xml
from core.weather_views import weather
from core.academy_views import (
    academy, education, education_course_detail, education_enroll,
    education_lesson, education_lesson_complete, education_bookmark,
    education_assessment, education_assessment_submit, education_dashboard,
    education_certificate, education_issue_certificate,
)
from core.services_views import services
from core.company_content_views import company_gallery, company_content_feed, company_portal_home
from core.knowledge_views import knowledge_article_detail, knowledge_book_detail, knowledge_domain_detail

urlpatterns = [
    path("", services, name="home"),
    path("agriculture/", lambda request: platform_page(request, "agriculture"), name="agriculture"),
    path("industry/", lambda request: platform_page(request, "industry"), name="industry"),
    path("research/", lambda request: platform_page(request, "research"), name="research"),
    path("knowledge/", lambda request: platform_page(request, "knowledge"), name="knowledge"),
    path("knowledge/article/<slug:slug>/", knowledge_article_detail, name="knowledge_article_detail"),
    path("knowledge/book/<slug:slug>/", knowledge_book_detail, name="knowledge_book_detail"),
    path("knowledge/domain/<slug:slug>/", knowledge_domain_detail, name="knowledge_domain_detail"),
    path("market/", lambda request: platform_page(request, "market"), name="market"),
    path("economy/", lambda request: platform_page(request, "economy"), name="economy"),
    path("studio/", lambda request: platform_page(request, "studio"), name="studio"),
    path("agents/", lambda request: platform_page(request, "agents"), name="agents"),
    path("search/", site_search, name="site_search"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),
    path("store/", store_home, name="store"),
    path("auctions/", auctions_home, name="auctions"),
    path("company-gallery/", company_gallery, name="company_gallery"),
    path("company-content/<slug:slug>/", company_content_feed, name="company_content_feed"),
    path("company/", lambda request: company_portal_home(request) if request.method == "POST" else platform_page(request, "company"), name="company"),
    path("company/<slug:slug>/", lambda request, slug: platform_page(request, "company"), name="company_detail"),
    path("about/", RedirectView.as_view(pattern_name="company", permanent=True), name="about"),
    path("contact/", RedirectView.as_view(pattern_name="company", permanent=True), name="contact"),
    path("weather/", weather, name="weather"),
    path("education/", education, name="education"),
    path("education/dashboard/", education_dashboard, name="education_dashboard"),
    path("education/certificate/<str:code>/", education_certificate, name="education_certificate"),
    path("education/course/<slug:slug>/", education_course_detail, name="education_course_detail"),
    path("education/course/<slug:slug>/enroll/", education_enroll, name="education_enroll"),
    path("education/course/<slug:slug>/lesson/<int:lesson_id>/", education_lesson, name="education_lesson"),
    path("education/course/<slug:slug>/lesson/<int:lesson_id>/complete/", education_lesson_complete, name="education_lesson_complete"),
    path("education/course/<slug:slug>/lesson/<int:lesson_id>/bookmark/", education_bookmark, name="education_bookmark"),
    path("education/course/<slug:slug>/assessment/<int:assessment_id>/", education_assessment, name="education_assessment"),
    path("education/course/<slug:slug>/assessment/<int:assessment_id>/submit/", education_assessment_submit, name="education_assessment_submit"),
    path("education/course/<slug:slug>/certificate/issue/", education_issue_certificate, name="education_issue_certificate"),
    path("academy/", academy, name="academy"),
    path("services/", services, name="services"),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
]

from core.newsletter_views import newsletter_home, newsletter_archive, newsletter_detail
urlpatterns += [path("newsletter/", newsletter_home, name="newsletter"), path("newsletter/archive/", newsletter_archive, name="newsletter_archive"), path("newsletter/<slug:slug>/", newsletter_detail, name="newsletter_detail")]

from core.blog_views import blog_home, blog_page
urlpatterns += [path("blog/", blog_home, name="blog"), path("blog/<path:slug>/", blog_page, name="blog_page")]
