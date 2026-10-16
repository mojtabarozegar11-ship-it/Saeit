from pathlib import Path
import re

from django.http import FileResponse, Http404, HttpResponse
from django.utils.cache import patch_cache_control

BASE_DIR = Path(__file__).resolve().parent.parent
AGRICULTURE_SLUGS = frozenset({
    "livestock", "horticulture", "greenhouse", "poultry", "aquaculture",
    "inputs", "seeds", "fertilizers", "pesticides", "offices",
    "water-soil", "machinery", "market",
})


def agriculture_index(request):
    if request.get_host().split(":")[0].lower() in {"mojplaywin.com", "www.mojplaywin.com"}:
        from core.views import platform_page
        return platform_page(request, "agriculture")
    page = BASE_DIR / "public" / "agriculture" / "index.html"
    if not page.is_file():
        raise Http404
    return HttpResponse(page.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")


def agriculture_guide(request, slug):
    if slug not in AGRICULTURE_SLUGS:
        raise Http404
    page = BASE_DIR / "public" / "agriculture" / slug / "index.html"
    if not page.is_file():
        raise Http404
    return HttpResponse(page.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")


def zomorod_hero_image(request, filename):
    # The URL captures only the stem before the fixed .webp suffix.
    if not re.fullmatch(r"[a-z0-9-]+", filename):
        raise Http404
    image = BASE_DIR / "core" / "static" / "site" / "heroes" / f"{filename}.webp"
    if not image.is_file():
        raise Http404
    response = FileResponse(image.open("rb"), content_type="image/webp")
    patch_cache_control(response, public=True, max_age=86400)
    return response
