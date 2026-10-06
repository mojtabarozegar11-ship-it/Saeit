
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from core.views import home, platform_page
from core.brand_views import branded_home, branded_page, branded_game
from core.brand import brand_for_request
from core.commerce_views import store_home, auctions_home
from core.seo_views import site_search
from core.brand_seo_views import branded_robots_txt, branded_sitemap_xml
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
    path("", branded_home, name="home"),
    path("games/first-realm/", branded_game, {"slug": "first-realm"}, name="mpw_first_realm"),
    path("products/", branded_page, {"page": "products"}, name="mpw_products"),
    path("games/", branded_page, {"page": "games"}, name="mpw_games"),
    path("worlds/", branded_page, {"page": "worlds"}, name="mpw_worlds"),
    path("news/", branded_page, {"page": "news"}, name="mpw_news"),
    path("community/", branded_page, {"page": "community"}, name="mpw_community"),
    path("support/", branded_page, {"page": "support"}, name="mpw_support"),
    path("ai/", branded_page, {"page": "ai"}, name="mpw_ai"),
    path("software/", branded_page, {"page": "software"}, name="mpw_software"),
    path("commerce/", branded_page, {"page": "commerce"}, name="mpw_commerce"),
    path("crypto-payments/", branded_page, {"page": "crypto-payments"}, name="mpw_crypto_payments"),
    path("blockchain/", branded_page, {"page": "blockchain"}, name="mpw_blockchain"),
    path("research-lab/", branded_page, {"page": "research-lab"}, name="mpw_research_lab"),
    path("game-factory/", branded_page, {"page": "game-factory"}, name="mpw_game_factory"),
    path("global-business/", branded_page, {"page": "global-business"}, name="mpw_global_business"),
    path("agro-industry/", branded_page, {"page": "agro-industry"}, name="mpw_agro_industry"),
    path("canada-vision/", branded_page, {"page": "canada-vision"}, name="mpw_canada_vision"),
    path("privacy/", branded_page, {"page": "privacy"}, name="mpw_privacy"),
    path("terms/", branded_page, {"page": "terms"}, name="mpw_terms"),
    path("cookies/", branded_page, {"page": "cookies"}, name="mpw_cookies"),
    path("agriculture/", lambda request: platform_page(request, "agriculture"), name="agriculture"),
    path("industry/", lambda request: platform_page(request, "industry"), name="industry"),
    path("research/", lambda request: platform_page(request, "research"), name="research"),
    path("knowledge/", lambda request: platform_page(request, "knowledge"), name="knowledge"),
    path("knowledge/article/<slug:slug>/", knowledge_article_detail, name="knowledge_article_detail"),
    path("knowledge/book/<slug:slug>/", knowledge_book_detail, name="knowledge_book_detail"),
    path("knowledge/domain/<slug:slug>/", knowledge_domain_detail, name="knowledge_domain_detail"),
    path("market/", lambda request: platform_page(request, "market"), name="market"),
    path("economy/", lambda request: platform_page(request, "economy"), name="economy"),
    path("studio/", lambda request: branded_page(request, "studio") if brand_for_request(request) else platform_page(request, "studio"), name="studio"),
    path("agents/", lambda request: platform_page(request, "agents"), name="agents"),
    path("search/", site_search, name="site_search"),
    path("robots.txt", branded_robots_txt, name="robots_txt"),
    path("sitemap.xml", branded_sitemap_xml, name="sitemap_xml"),
    path("store/", store_home, name="store"),
    path("auctions/", auctions_home, name="auctions"),
    path("company-gallery/", company_gallery, name="company_gallery"),
    path("company-content/<slug:slug>/", company_content_feed, name="company_content_feed"),
    path("company/", lambda request: company_portal_home(request) if request.method == "POST" else platform_page(request, "company"), name="company"),
    path("company/<slug:slug>/", lambda request, slug: platform_page(request, "company"), name="company_detail"),
    path("about/", lambda request: branded_page(request, "about") if brand_for_request(request) else RedirectView.as_view(pattern_name="company", permanent=True)(request), name="about"),
    path("contact/", lambda request: branded_page(request, "contact") if brand_for_request(request) else RedirectView.as_view(pattern_name="company", permanent=True)(request), name="contact"),
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
    path("services/", lambda request: branded_page(request, "services") if brand_for_request(request) else services(request), name="services"),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
]

from core.newsletter_views import newsletter_home, newsletter_archive, newsletter_detail
urlpatterns += [path("newsletter/", newsletter_home, name="newsletter"), path("newsletter/archive/", newsletter_archive, name="newsletter_archive"), path("newsletter/<slug:slug>/", newsletter_detail, name="newsletter_detail")]

from core.blog_views import blog_home, blog_page
urlpatterns += [path("blog/", blog_home, name="blog"), path("blog/<path:slug>/", blog_page, name="blog_page")]
