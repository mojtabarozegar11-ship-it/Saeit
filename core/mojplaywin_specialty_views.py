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
    return response
