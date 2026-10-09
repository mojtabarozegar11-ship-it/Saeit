from django.http import HttpResponse
from django.views.decorators.http import require_GET
from .brand import brand_for_request
from .models import Product
from django.db.models import Q
from xml.sax.saxutils import escape

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
        paths.extend(f"store/product/{pk}/" for pk in Product.objects.filter(active=True, knowledge_article__published=True, metadata__brand_code="mojplaywin").filter(Q(factory_managed=False) | Q(factory_release_gate__status="approved")).order_by("pk").distinct().values_list("pk", flat=True).iterator(chunk_size=500))
        urls = "".join(f"<url><loc>{escape('https://mojplaywin.com/' + path)}</loc></url>" for path in paths)
        body = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
        return HttpResponse(body, content_type="application/xml")
    from .seo_views import sitemap_xml
    return sitemap_xml(request)
