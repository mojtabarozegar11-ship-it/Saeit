import json
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import KnowledgeArticle, Product
from .newsletter_models import NewsletterStory


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
            results.append((_score(q, x.title, x.content), {"type": "دانش", "title": x.title, "summary": x.content[:280], "url": "/knowledge/"}))
        products = Product.objects.filter(active=True).filter(Q(title__icontains=q) | Q(product_type__icontains=q))[:50]
        for x in products:
            results.append((_score(q, x.title, x.product_type), {"type": "فروشگاه", "title": x.title, "summary": f"{x.product_type} · {x.price} {x.currency}", "url": "/store/"}))
        aliases = ("شرکت کشت و صنعت زمرد ملل", "زمرد ملل", "مجتبی روزگار", "محقق و پژوهشگر", "مدیرعامل", "مدیر عامل")
        if any(_norm(q) in _norm(alias) or _norm(alias) in _norm(q) for alias in aliases):
            results.append((100, {"type": "شرکت", "title": "شرکت کشت و صنعت زمرد ملل", "summary": "مجتبی روزگار — محقق و پژوهشگر / مدیرعامل شرکت کشت و صنعت زمرد ملل", "url": "/company/"}))
    results.sort(key=lambda item: item[0], reverse=True)
    return render(request, "core/search.html", {"q": q, "results": [item[1] for item in results[:50]]})


@require_GET
def robots_txt(request):
    body = "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /api/\nSitemap: https://zomorodmelal.ir/sitemap.xml\n"
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


@require_GET
def sitemap_xml(request):
    urls = ["/", "/company/", "/company/executive/", "/research/", "/knowledge/", "/market/", "/agriculture/", "/industry/", "/agents/", "/newsletter/", "/newsletter/archive/", "/store/", "/auctions/"]
    company_ranges = {"department": 9, "unit": 9, "genetics": 12, "product": 29, "statutory": 18, "craft": 2, "project": 5, "channel": 4, "social": 3, "future": 4}
    for kind, count in company_ranges.items():
        urls.extend(f"/company/{kind}-{i}/" for i in range(1, count + 1))
    stories = NewsletterStory.objects.filter(status="published", published_at__lte=timezone.now()).values_list("slug", flat=True)
    urls += [f"/newsletter/{slug}/" for slug in stories]
    items = "".join(f"<url><loc>https://zomorodmelal.ir{u}</loc></url>" for u in urls)
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
