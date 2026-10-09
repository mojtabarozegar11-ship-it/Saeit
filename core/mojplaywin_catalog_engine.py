"""Read-only public catalog engine. Never activates, sells or releases a factory product."""
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_GET
from .brand import brand_for_request
from .models import Product


@require_GET
def public_catalog(request):
    brand = brand_for_request(request)
    if not brand or brand.code != "mojplaywin":
        raise Http404
    try:
        limit = int(request.GET.get("limit", "24"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "limit must be an integer"}, status=400)
    if not 1 <= limit <= 100:
        return JsonResponse({"error": "limit must be between 1 and 100"}, status=400)
    queryset = Product.objects.filter(active=True, knowledge_article__published=True, metadata__brand_code="mojplaywin").order_by("-id")
    # No factory activation or release bypass: only already-public products are shown.
    items = [{"id": p.pk, "title": p.title, "type": p.product_type,
              "price": str(p.price), "currency": p.currency,
              "url": "/store/product/%s/" % p.pk} for p in queryset[:limit]]
    response = JsonResponse({"products": items, "count": len(items), "limit": limit})
    response["Cache-Control"] = "public, max-age=60"
    return response
