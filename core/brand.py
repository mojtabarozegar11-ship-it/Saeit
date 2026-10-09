from dataclasses import dataclass

@dataclass(frozen=True)
class Brand:
    code: str
    name: str
    domain: str
    template: str
    language: str = "en"
    direction: str = "ltr"
    seo_title: str = ""
    seo_description: str = ""

STATIC_BRANDS = {
    "mojplaywin.com": Brand("mojplaywin", "MojPlayWin", "mojplaywin.com", "brands/mojplaywin/home.html"),
    "www.mojplaywin.com": Brand("mojplaywin", "MojPlayWin", "mojplaywin.com", "brands/mojplaywin/home.html"),
}

def brand_for_request(request):
    host = request.get_host().split(":", 1)[0].lower().rstrip(".")
    try:
        from .models import BrandSite
        site = BrandSite.objects.filter(active=True, primary_domain=host).first()
        if site is None:
            for candidate in BrandSite.objects.filter(active=True):
                if host in (candidate.aliases or []):
                    site = candidate
                    break
        if site is not None:
            return Brand(
                site.code, site.name, site.primary_domain,
                f"brands/{site.theme_key}/home.html",
                site.default_language, site.direction,
                site.seo_title, site.seo_description,
            )
    except Exception:
        # Startup/migration-safe fallback; database failures must not make a
        # configured public brand disappear while migrations are being applied.
        pass
    return STATIC_BRANDS.get(host)
