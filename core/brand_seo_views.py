from django.http import HttpResponse
from django.views.decorators.http import require_GET
from .brand import brand_for_request

@require_GET
def branded_robots_txt(request):
    brand = brand_for_request(request)
    if brand and brand.code == "mojplaywin":
        return HttpResponse("User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /api/\nSitemap: https://mojplaywin.com/sitemap.xml\n", content_type="text/plain; charset=utf-8")
    from .seo_views import robots_txt
    return robots_txt(request)

@require_GET
def branded_sitemap_xml(request):
    brand = brand_for_request(request)
    if brand and brand.code == "mojplaywin":
        paths = ["", "store/", "products/", "services/", "games/", "games/first-realm/", "worlds/", "ai/", "software/", "commerce/", "blockchain/", "crypto-payments/", "research-lab/", "studio/", "global-business/", "agro-industry/", "canada-vision/", "news/", "community/", "support/", "about/", "contact/", "privacy/", "terms/", "cookies/"]
        urls = "".join(f"<url><loc>https://mojplaywin.com/{path}</loc></url>" for path in paths)
        body = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
        return HttpResponse(body, content_type="application/xml")
    from .seo_views import sitemap_xml
    return sitemap_xml(request)
