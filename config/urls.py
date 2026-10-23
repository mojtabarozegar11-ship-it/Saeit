
from django.contrib import admin
from django.views.generic import TemplateView
from django.urls import include, path
from django.views.generic import RedirectView
from command_center.views import dashboard as staff_dashboard

from core.views import home, platform_page, taniya_studio
from core.mojplaywin_views import venture
from core.commerce_views import store_home, auctions_home
from core.crown_checkout import crown_cosmetic_checkout
from core.product_seo_views import product_detail
from core.seo_views import site_search, robots_txt, sitemap_xml, persian_author_profile
from core.weather_views import weather
from core.academy_views import (
    academy, education, education_course_detail, education_enroll,
    education_lesson, education_lesson_complete, education_bookmark,
    education_assessment, education_assessment_submit, education_dashboard,
    education_certificate, education_issue_certificate,
)
from core.services_views import services
from core.zomorod_public_views import agriculture_index, agriculture_guide, zomorod_hero_image
from core.company_content_views import company_gallery, company_content_feed, company_portal_home
from core.knowledge_views import knowledge_article_detail, knowledge_book_detail, knowledge_domain_detail

urlpatterns = [
    path("", services, name="home"),
    path("authors/mojtaba-rozegar/", persian_author_profile, name="mojtaba_roozegar_author_profile"),
    path("ghanadi/", TemplateView.as_view(template_name="core/ghanadi.html"), name="ghanadi"),
    path("agriculture/", agriculture_index, name="agriculture"),
    path("agriculture/assets/zomorod-olive-v1/<str:filename>.webp", zomorod_hero_image, name="agriculture_hero_asset"),
    path("agriculture/<slug:slug>/", agriculture_guide, name="agriculture_guide"),
    path("amozeshgah/assets/zomorod-education-v1/<str:filename>.webp", zomorod_hero_image, name="education_hero_asset"),
    path("static/site/heroes/<str:filename>.webp", zomorod_hero_image, name="site_hero_image"),
    path("industry/", lambda request: platform_page(request, "industry"), name="industry"),
    path("ventures/<slug:slug>/", venture, name="mojplaywin_venture"),
    path("research/", lambda request: platform_page(request, "research"), name="research"),
    path("knowledge/", lambda request: platform_page(request, "knowledge"), name="knowledge"),
    path("knowledge/article/<slug:slug>/", knowledge_article_detail, name="knowledge_article_detail"),
    path("knowledge/book/<slug:slug>/", knowledge_book_detail, name="knowledge_book_detail"),
    path("knowledge/domain/<slug:slug>/", knowledge_domain_detail, name="knowledge_domain_detail"),
    path("market/", lambda request: platform_page(request, "market"), name="market"),
    path("economy/", lambda request: platform_page(request, "economy"), name="economy"),
    path("studio/", lambda request: platform_page(request, "studio"), name="studio"),
    path("taniya/", taniya_studio, name="taniya_studio"),
    path("agents/", lambda request: platform_page(request, "agents"), name="agents"),
    path("search/", site_search, name="site_search"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),
    path("store/", store_home, name="store"),
    path("store/product/<int:product_id>/", product_detail, name="store_product_detail"),
    path("store/crown/<int:product_id>/checkout/", crown_cosmetic_checkout, name="crown_cosmetic_checkout"),
    path("auctions/", auctions_home, name="auctions"),
    path("company-gallery/", company_gallery, name="company_gallery"),
    path("company-content/<slug:slug>/", company_content_feed, name="company_content_feed"),
    path("company/", lambda request: company_portal_home(request) if request.method == "POST" else platform_page(request, "company"), name="company"),
    path("company/<slug:slug>/", lambda request, slug: platform_page(request, "company"), name="company_detail"),
    path("about/", RedirectView.as_view(pattern_name="company", permanent=True), name="about"),
    path("contact/", RedirectView.as_view(pattern_name="company", permanent=True), name="contact"),
    path("weather/", weather, name="weather"),
    # Canonical education platform under the requested company path.
    path("amozeshgah/", education, name="education"),
    path("amozeshgah/dashboard/", education_dashboard, name="education_dashboard"),
    path("amozeshgah/certificate/<str:code>/", education_certificate, name="education_certificate"),
    path("amozeshgah/course/<slug:slug>/", education_course_detail, name="education_course_detail"),
    path("amozeshgah/course/<slug:slug>/enroll/", education_enroll, name="education_enroll"),
    path("amozeshgah/course/<slug:slug>/lesson/<int:lesson_id>/", education_lesson, name="education_lesson"),
    path("amozeshgah/course/<slug:slug>/lesson/<int:lesson_id>/complete/", education_lesson_complete, name="education_lesson_complete"),
    path("amozeshgah/course/<slug:slug>/lesson/<int:lesson_id>/bookmark/", education_bookmark, name="education_bookmark"),
    path("amozeshgah/course/<slug:slug>/assessment/<int:assessment_id>/", education_assessment, name="education_assessment"),
    path("amozeshgah/course/<slug:slug>/assessment/<int:assessment_id>/submit/", education_assessment_submit, name="education_assessment_submit"),
    path("amozeshgah/course/<slug:slug>/certificate/issue/", education_issue_certificate, name="education_issue_certificate"),
    # Keep the previous public paths available for bookmarks and older links.
    path("education/", education, name="education_legacy"),
    path("education/dashboard/", education_dashboard, name="education_dashboard_legacy"),
    path("education/certificate/<str:code>/", education_certificate, name="education_certificate_legacy"),
    path("education/course/<slug:slug>/", education_course_detail, name="education_course_detail_legacy"),
    path("education/course/<slug:slug>/enroll/", education_enroll, name="education_enroll_legacy"),
    path("education/course/<slug:slug>/lesson/<int:lesson_id>/", education_lesson, name="education_lesson_legacy"),
    path("education/course/<slug:slug>/lesson/<int:lesson_id>/complete/", education_lesson_complete, name="education_lesson_complete_legacy"),
    path("education/course/<slug:slug>/lesson/<int:lesson_id>/bookmark/", education_bookmark, name="education_bookmark_legacy"),
    path("education/course/<slug:slug>/assessment/<int:assessment_id>/", education_assessment, name="education_assessment_legacy"),
    path("education/course/<slug:slug>/assessment/<int:assessment_id>/submit/", education_assessment_submit, name="education_assessment_submit_legacy"),
    path("education/course/<slug:slug>/certificate/issue/", education_issue_certificate, name="education_issue_certificate_legacy"),
    path("academy/", academy, name="academy"),
    path("services/", services, name="services"),
    path("staff/command-center/", include("command_center.urls")),
    path("staff/", staff_dashboard, name="staff_management"),
    path("farnaz/", include("farnaz.urls")),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
]

from core.newsletter_views import newsletter_home, newsletter_archive, newsletter_detail
urlpatterns += [path("newsletter/", newsletter_home, name="newsletter"), path("newsletter/archive/", newsletter_archive, name="newsletter_archive"), path("newsletter/<slug:slug>/", newsletter_detail, name="newsletter_detail")]

from core.blog_views import blog_home, blog_page
urlpatterns += [path("blog/", blog_home, name="blog"), path("blog/<path:slug>/", blog_page, name="blog_page")]
