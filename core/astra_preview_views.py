"""Public, read-only MojPlayWin Astra preview pages; no bundle or checkout access."""
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_safe

from .brand import brand_for_request

PUBLIC_SLUGS = frozenset({
    "circuit-courier", "farm-procurement-audit",
    "farm-water-land-margin-audit", "orchard-decision-audit",
})


@require_safe
def astra_preview_page(request, slug=None):
    brand = brand_for_request(request)
    if brand is None or brand.code != "mojplaywin":
        raise Http404("Not found")
    if slug is not None and slug not in PUBLIC_SLUGS:
        raise Http404("Unknown preview")

    base = Path(settings.BASE_DIR).resolve().parent / "mojplaywin.com" / "factory-previews"
    target = base / slug / "index.html" if slug else base / "index.html"
    if (base.is_symlink() or not base.is_dir() or
            target.parent.is_symlink() or target.is_symlink() or
            not target.is_file() or not 0 < target.stat().st_size <= 150_000):
        raise Http404("Preview not available")
    return HttpResponse(target.read_bytes(), content_type="text/html; charset=utf-8")
