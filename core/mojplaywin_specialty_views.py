"""Independent editorial pages for MojPlayWin specialty products and services."""
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .brand import brand_for_request
from .mojplaywin_specialties import SPECIALTIES


@require_GET
def specialty_page(request, kind, slug):
    brand = brand_for_request(request)
    if getattr(brand, "code", None) != "mojplaywin":
        raise Http404
    key = f"{kind}/{slug}"
    item = SPECIALTIES.get(key)
    if item is None:
        raise Http404
    siblings = [
        {"title": entry["title"], "url": f"/{kind}/{name.split('/', 1)[1]}/"}
        for name, entry in SPECIALTIES.items()
        if entry["kind"] == kind and name != key
    ]
    response = render(
        request, "brands/mojplaywin/specialty.html",
        {"brand": brand, "specialty": item, "kind": kind,
         "siblings": siblings, "specialty_key": key},
    )
    response["X-Robots-Tag"] = "noindex, follow, noarchive"
    response["Cache-Control"] = "private, no-store"
    return response


@require_GET
def specialty_directory(request, kind):
    """Editorial directory only; preserve the legacy services page on other hosts."""
    if kind not in ("products", "services"):
        raise Http404
    brand = brand_for_request(request)
    if getattr(brand, "code", None) != "mojplaywin":
        if kind == "services":
            from .services_views import services
            return services(request)
        raise Http404
    entries = [
        {"title": item["title"], "focus": item["focus"], "url": f"/{key}/"}
        for key, item in SPECIALTIES.items() if item["kind"] == kind
    ]
    response = render(request, "brands/mojplaywin/specialty_directory.html",
                      {"brand": brand, "kind": kind, "entries": entries})
    response["X-Robots-Tag"] = "noindex, follow, noarchive"
    response["Cache-Control"] = "private, no-store"
    return response
