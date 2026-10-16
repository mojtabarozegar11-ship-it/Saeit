from pathlib import Path

from django.http import FileResponse, Http404, HttpResponse
from django.utils.cache import patch_cache_control

BASE_DIR = Path(__file__).resolve().parent.parent
AGRICULTURE_SLUGS = frozenset({
    "livestock", "horticulture", "greenhouse", "poultry", "aquaculture",
    "inputs", "seeds", "fertilizers", "pesticides", "offices",
    "water-soil", "machinery", "market",
})


def agriculture_index(request):
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
    # Restrict this public endpoint to existing WebP hero files; never join
    # arbitrary user paths into the filesystem.
    if "/" in filename or "\\" in filename or not filename.endswith(".webp"):
        raise Http404
    image = BASE_DIR / "core" / "static" / "site" / "heroes" / filename
    if not image.is_file():
        raise Http404
    response = FileResponse(image.open("rb"), content_type="image/webp")
    patch_cache_control(response, public=True, max_age=86400)
    return response
