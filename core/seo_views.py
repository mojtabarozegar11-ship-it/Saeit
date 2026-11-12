import json
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from .models import KnowledgeArticle, Product
from .knowledge_agent_models import KnowledgeBook, KnowledgeDomain
from .newsletter_models import NewsletterStory
from .blog_models import BlogPage

INDEXNOW_KEY = "f5e9e3dccc5c2511c452f26b011ec43e"


def _norm(value):
    return " ".join(str(value or "").replace("ي", "ی").replace("ك", "ک").replace("‌", " ").split()).strip().lower()


def _score(q, *fields):
    qn = _norm(q)
    score = 0
    weights = (10, 5, 2)
    for i, value in enumerate(fields):
        text = _norm(value)
        if not text:
            continue
        if qn == text:
            score += weights[i] * 3
        elif qn in text:
            score += weights[i]
        for token in qn.split():
            if token and token in text:
                score += max(1, weights[i] // 2)
    return score


def site_search(request):
    q = str(request.GET.get("q", "")).strip()[:120]
    results = []
    if q:
        stories = NewsletterStory.objects.filter(status="published", published_at__lte=timezone.now()).filter(
            Q(title__icontains=q) | Q(summary__icontains=q) | Q(body__icontains=q) | Q(seo_keywords__icontains=q)
        )[:50]
        for x in stories:
            results.append((_score(q, x.title, x.summary, x.body), {"type": "خبر", "title": x.title, "summary": x.summary, "url": f"/newsletter/{x.slug}/"}))
        articles = KnowledgeArticle.objects.filter(published=True).filter(Q(title__icontains=q) | Q(content__icontains=q))[:50]
        for x in articles:
            results.append((_score(q, x.title, x.content), {"type": "دانش", "title": x.title, "summary": x.content[:280], "url": f"/knowledge/article/{x.slug}/"}))
        books = KnowledgeBook.objects.filter(Q(title__icontains=q) | Q(domain__icontains=q) | Q(objective__icontains=q))[:50]
        for x in books:
            results.append((_score(q, x.title, x.domain, x.objective), {"type": "کتاب", "title": x.title, "summary": x.objective[:280], "url": f"/knowledge/book/{x.code}/"}))
        domains = KnowledgeDomain.objects.filter(active=True).filter(Q(title__icontains=q) | Q(scientific_scope__icontains=q))[:50]
        for x in domains:
            results.append((_score(q, x.title, x.scientific_scope), {"type": "حوزه دانش", "title": x.title, "summary": x.scientific_scope[:280], "url": f"/knowledge/domain/{x.code}/"}))
        products = Product.objects.filter(active=True).filter(Q(title__icontains=q) | Q(product_type__icontains=q))[:50]
        for x in products:
            results.append((_score(q, x.title, x.product_type), {"type": "فروشگاه", "title": x.title, "summary": f"{x.product_type} · {x.price} {x.currency}", "url": f"/store/product/{x.pk}/"}))
        aliases = ("شرکت کشت و صنعت زمرد ملل", "زمرد ملل", "مجتبی روزگار", "محقق و پژوهشگر", "مدیرعامل", "مدیر عامل")
        if any(_norm(q) in _norm(alias) or _norm(alias) in _norm(q) for alias in aliases):
            results.append((100, {"type": "شرکت", "title": "شرکت کشت و صنعت زمرد ملل", "summary": "مجتبی روزگار — محقق و پژوهشگر / مدیرعامل شرکت کشت و صنعت زمرد ملل", "url": "/company/"}))
    results.sort(key=lambda item: item[0], reverse=True)
    return render(request, "core/search.html", {"q": q, "results": [item[1] for item in results[:50]]})


@require_GET
def robots_txt(request):
    """Expose the canonical host's public sitemap without changing private-path rules."""
    host = request.get_host().split(":")[0].lower()
    # Private exclusions come first for conservative first-match robots parsers.
    if host in {"mojplaywin.com", "www.mojplaywin.com"}:
        body = (
            "User-agent: *\n"
            "Disallow: /admin/\n"
            "Disallow: /api/\n"
            "Allow: /\n"
            "Sitemap: https://mojplaywin.com/sitemap.xml\n"
        )
    else:
        body = (
            "User-agent: *\n"
            "Disallow: /admin/\n"
            "Disallow: /api/\n"
            "Disallow: /__zm_\n"
            "Disallow: /site-heritage/\n"
            "Disallow: /zm-agriculture-guides/\n"
            "Allow: /\n"
            "Sitemap: https://zomorodmelal.ir/sitemap.xml\n"
            "Sitemap: https://zomorodmelal.ir/topics/sitemap.xml\n"
            "Sitemap: https://zomorodmelal.ir/ghanadi/sitemap.xml\n"
        )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")

@require_GET
def indexnow_key(request, key):
    """Public IndexNow verification file for the MojPlayWin host only."""
    host = request.get_host().split(":")[0].lower()
    if host not in {"mojplaywin.com", "www.mojplaywin.com"} or key != INDEXNOW_KEY:
        return HttpResponse(status=404)
    return HttpResponse(INDEXNOW_KEY + "\n", content_type="text/plain; charset=utf-8")


@require_GET
def sitemap_xml(request):
    # The two brands share a Django URLconf but must never share sitemap origins.
    # Independent cPanel sitemap sources are outside this Django fallback.
    host = request.get_host().split(":")[0].lower()
    if host in {"mojplaywin.com", "www.mojplaywin.com"}:
        # WARNING: this is the Django-only emergency fallback, NOT the native
        # cPanel/PHP 152+ page publisher. Do not deploy before proving routing.
        # Never silently replace the native map with a one-page response.
        from django.conf import settings
        from pathlib import Path
        from urllib.parse import urlsplit
        from xml.etree import ElementTree

        source = (Path(settings.BASE_DIR) / "docs/seo/evidence/"
                  "mpw-public-152-page-reconstructed-baseline-20261112.xml")
        try:
            if source.is_symlink() or not source.is_file() or source.stat().st_size > 262144:
                raise ValueError("MojPlayWin fallback baseline unavailable")
            payload = source.read_bytes()
            root = ElementTree.fromstring(payload)
            ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
            if root.tag != ns + "urlset":
                raise ValueError("MojPlayWin fallback is not a sitemap urlset")
            urls = []
            for entry in root.findall(ns + "url"):
                loc = entry.findtext(ns + "loc")
                parts = urlsplit(loc or "")
                if (not loc or loc != loc.strip() or parts.scheme != "https"
                        or parts.netloc != "mojplaywin.com" or parts.query
                        or parts.fragment or not parts.path.startswith("/")
                        or parts.username or parts.password
                        or any(parts.path.startswith("/" + private + "/") for private
                               in ("admin", "api", "checkout", "private", "download",
                                   "account", "orders"))):
                    raise ValueError("Nonpublic or foreign sitemap URL in fallback")
                urls.append(loc)
            required = {
                "https://mojplaywin.com/store/",
                "https://mojplaywin.com/store/product/72/",
                "https://mojplaywin.com/store/product/225/",
                "https://mojplaywin.com/store/product/879/",
            }
            if len(urls) < 152 or len(urls) != len(set(urls)) or not required.issubset(urls):
                raise ValueError("Incomplete MojPlayWin fallback sitemap")
        except (OSError, ValueError, ElementTree.ParseError):
            # Transient 503 is safer than a valid-looking sitemap with 151
            # missing pages. It must not be used as normal production routing.
            response = HttpResponse("MojPlayWin fallback sitemap unavailable",
                                    content_type="text/plain; charset=utf-8",
                                    status=503)
            response["Retry-After"] = "3600"
            response["Cache-Control"] = "no-store"
            return response
        return HttpResponse(payload, content_type="application/xml")
    # Sitemap entries must be canonical public destinations, not redirects or gated pages.
    urls = ["/", "/company/", "/company/executive/", "/services/", "/amozeshgah/", "/research/", "/research/projects/", "/knowledge/", "/market/", "/agriculture/", "/industry/", "/gold/", "/vehicles/", "/marketing/", "/chain-stores/", "/agents/", "/weather/", "/economy/", "/studio/", "/newsletter/", "/blog/", "/store/", "/agriculture/free-tools/20261025/", "/auctions/", "/faremah/", "/ghanadi/", "/ghanadi/cafe-shiraz/", "/company-gallery/", "/agriculture/genetics/", "/en/authors/mojtaba-rozegar/", "/authors/mojtaba-rozegar/"]
    urls += [f"/blog/{quote(str(code), safe='')}/" for code in BlogPage.objects.filter(active=True).values_list("code", flat=True)]
    company_ranges = {"department": 9, "unit": 9, "genetics": 12, "product": 55, "statutory": 18, "craft": 2, "project": 5, "channel": 4, "social": 3, "future": 4}
    for kind, count in company_ranges.items():
        urls.extend(f"/company/{kind}-{i}/" for i in range(1, count + 1))
    stories = NewsletterStory.objects.filter(status="published", published_at__lte=timezone.now()).values_list("slug", flat=True)
    urls += [f"/newsletter/{slug}/" for slug in stories]
    articles = KnowledgeArticle.objects.filter(published=True).values_list("slug", flat=True)
    urls += [f"/knowledge/article/{slug}/" for slug in articles]
    books = KnowledgeBook.objects.filter(status="published").values_list("code", flat=True)
    urls += [f"/knowledge/book/{code}/" for code in books]
    domains = KnowledgeDomain.objects.filter(active=True).values_list("code", flat=True)
    urls += [f"/knowledge/domain/{code}/" for code in domains]
    urls += [f"/store/product/{pk}/" for pk in Product.objects.filter(active=True).values_list("pk",flat=True)]
    items = "".join(f"<url><loc>{xml_escape('https://zomorodmelal.ir' + u)}</loc></url>" for u in dict.fromkeys(urls))
    return HttpResponse(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>', content_type="application/xml")


def organization_jsonld():
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": "https://zomorodmelal.ir/#organization",
        "name": "شرکت کشت و صنعت زمرد ملل",
        "legalName": "شرکت کشت و صنعت زمرد ملل",
        "url": "https://zomorodmelal.ir/",
        "logo": "https://zomorodmelal.ir/static/site/company/company-logo.png",
        "telephone": "+989022048691",
        "foundingDate": "2019-11-07",
        "description": "شرکت کشت و صنعت زمرد ملل؛ پژوهش، دانش، کشاورزی، صنعت و توسعه فناوری.",
        "employee": {"@type": "Person", "name": "مجتبی روزگار", "jobTitle": "محقق و پژوهشگر / مدیرعامل شرکت کشت و صنعت زمرد ملل"}
    }, ensure_ascii=False)


# zm-author-persian-view-20261023: a real 200 HTML response, not a canonical-damaging 301.
@require_GET
def persian_author_profile(request):
    from pathlib import Path
    from django.conf import settings

    page = Path(settings.BASE_DIR) / "public/authors/mojtaba-rozegar/index.html"
    if page.is_symlink() or not page.is_file():
        return HttpResponse(status=404)
    return HttpResponse(page.read_bytes(), content_type="text/html; charset=utf-8")
