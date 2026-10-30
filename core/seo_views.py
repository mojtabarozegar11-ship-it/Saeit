import json
from django.db.models import Q
from django.http import HttpResponse
from django.db import DatabaseError
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from .models import KnowledgeArticle, Product
from .knowledge_agent_models import KnowledgeBook, KnowledgeDomain
from .newsletter_models import NewsletterStory
from .blog_models import BlogPage
from .public_catalog_guard import missing_public_tables, mark_public_data_unavailable


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


def _site_search_with_schema(request):
    q = str(request.GET.get("q", "")).strip()[:120]
    results = []
    if q:
        stories = NewsletterStory.objects.filter(status="published", published_at__lte=timezone.now()).filter(
            Q(title__icontains=q) | Q(summary__icontains=q) | Q(body__icontains=q) | Q(seo_keywords__icontains=q)
        )[:50]
        for x in stories:
            results.append((_score(q, x.title, x.summary, x.body), {"type": "خبر", "title": x.title, "summary": x.summary, "url": f"/newsletter/{quote(str(x.slug), safe='')}/"}))
        articles = KnowledgeArticle.objects.filter(published=True).filter(Q(title__icontains=q) | Q(content__icontains=q))[:50]
        for x in articles:
            results.append((_score(q, x.title, x.content), {"type": "دانش", "title": x.title, "summary": str(x.content or "")[:280], "url": f"/knowledge/article/{quote(str(x.slug), safe='')}/"}))
        books = KnowledgeBook.objects.filter(status="published").filter(Q(title__icontains=q) | Q(domain__icontains=q) | Q(objective__icontains=q))[:50]
        for x in books:
            results.append((_score(q, x.title, x.domain, x.objective), {"type": "کتاب", "title": x.title, "summary": str(x.objective or "")[:280], "url": f"/knowledge/book/{quote(str(x.code), safe='')}/"}))
        domains = KnowledgeDomain.objects.filter(active=True).filter(Q(title__icontains=q) | Q(scientific_scope__icontains=q))[:50]
        for x in domains:
            results.append((_score(q, x.title, x.scientific_scope), {"type": "حوزه دانش", "title": x.title, "summary": str(x.scientific_scope or "")[:280], "url": f"/knowledge/domain/{quote(str(x.code), safe='')}/"}))
        products = Product.objects.filter(active=True).filter(Q(title__icontains=q) | Q(product_type__icontains=q))[:50]
        for x in products:
            results.append((_score(q, x.title, x.product_type), {"type": "فروشگاه", "title": x.title, "summary": f"{x.product_type or ''} · {x.price} {x.currency or ''}", "url": f"/store/product/{x.pk}/"}))
        aliases = ("شرکت کشت و صنعت زمرد ملل", "زمرد ملل", "مجتبی روزگار", "محقق و پژوهشگر", "مدیرعامل", "مدیر عامل")
        if any(_norm(q) in _norm(alias) or _norm(alias) in _norm(q) for alias in aliases):
            results.append((100, {"type": "شرکت", "title": "شرکت کشت و صنعت زمرد ملل", "summary": "مجتبی روزگار — محقق و پژوهشگر / مدیرعامل شرکت کشت و صنعت زمرد ملل", "url": "/company/"}))
    # Stable tie-breaking prevents search results flickering across DB query orders.
    results.sort(key=lambda item: (-item[0], _norm(item[1]["type"]),
                                   _norm(item[1]["title"]), item[1]["url"]))
    return render(request, "core/search.html", {"q": q, "results": [item[1] for item in results[:50]]})


def site_search(request):
    """Fail closed on incomplete or unavailable search schema; never claim zero results."""
    if missing_public_tables(
        NewsletterStory, KnowledgeArticle, KnowledgeBook, KnowledgeDomain, Product,
    ):
        return _unavailable_search()
    try:
        return _site_search_with_schema(request)
    except DatabaseError:
        # The schema may change or the DB may disconnect after introspection.
        return _unavailable_search()


def _unavailable_search():
    response = HttpResponse(
        '<!doctype html><html lang="fa" dir="rtl"><head>'
        '<meta charset="utf-8"><title>جست‌وجو موقتاً در دسترس نیست</title>'
        '</head><body><main><h1>جست‌وجو موقتاً در دسترس نیست</h1>'
        '<p role="status">نتایج جست‌وجو در حال حاضر قابل بازیابی نیستند؛ '
        'این وضعیت به معنای نبود اطلاعات نیست.</p>'
        '<p><a href="/">بازگشت به صفحه اصلی</a></p>'
        '</main></body></html>',
        status=503, content_type="text/html; charset=utf-8",
    )
    response["Retry-After"] = "300"
    return mark_public_data_unavailable(response)


@require_GET
def robots_txt(request):
    body = "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /api/\nSitemap: https://zomorodmelal.ir/sitemap.xml\n"
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


def _unavailable_sitemap():
    # A temporary schema outage is not an empty sitemap and must not be cached.
    response = HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?><error>Temporarily unavailable</error>',
        status=503, content_type="application/xml",
    )
    response["Retry-After"] = "300"
    return mark_public_data_unavailable(response)


@require_GET
def sitemap_xml(request):
    if missing_public_tables(
        BlogPage, NewsletterStory, KnowledgeArticle, KnowledgeBook,
        KnowledgeDomain, Product,
    ):
        return _unavailable_sitemap()
    urls = ["/", "/company/", "/company/executive/", "/research/", "/knowledge/", "/market/", "/agriculture/", "/industry/", "/agents/", "/education/", "/weather/", "/economy/", "/studio/", "/newsletter/", "/blog/", "/store/", "/auctions/", "/ghanadi/", "/company-gallery/", "/agriculture/genetics/", "/en/authors/mojtaba-rozegar/", "/authors/mojtaba-rozegar/"]
    try:
        urls += [f"/blog/{quote(str(code), safe='')}/" for code in BlogPage.objects.filter(active=True).values_list("code", flat=True)]
        company_ranges = {"department": 9, "unit": 9, "genetics": 12, "product": 55, "statutory": 18, "craft": 2, "project": 5, "channel": 4, "social": 3, "future": 4}
        for kind, count in company_ranges.items():
            urls.extend(f"/company/{kind}-{i}/" for i in range(1, count + 1))
        stories = NewsletterStory.objects.filter(status="published", published_at__lte=timezone.now()).values_list("slug", flat=True)
        urls += [f"/newsletter/{quote(str(slug), safe='')}/" for slug in stories]
        articles = KnowledgeArticle.objects.filter(published=True).values_list("slug", flat=True)
        urls += [f"/knowledge/article/{quote(str(slug), safe='')}/" for slug in articles]
        books = KnowledgeBook.objects.filter(status="published").values_list("code", flat=True)
        urls += [f"/knowledge/book/{quote(str(code), safe='')}/" for code in books]
        domains = KnowledgeDomain.objects.filter(active=True).values_list("code", flat=True)
        urls += [f"/knowledge/domain/{quote(str(code), safe='')}/" for code in domains]
        urls += [f"/store/product/{pk}/" for pk in Product.objects.filter(active=True).values_list("pk",flat=True)]
    except DatabaseError:
        return _unavailable_sitemap()
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


# zm-author-persian-view-20261023: preserve the public 200 HTML route without redirect.
# The author profile is a public static document, not a database view.
# Resolve every path component relative to a pinned directory descriptor:
# O_NOFOLLOW on the final HTML alone does not protect symlinked parent dirs.
def _read_author_html(base_dir):
    import os
    import stat

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_fd = os.open(str(base_dir), directory_flags)
    try:
        for segment in ("public", "authors", "mojtaba-rozegar"):
            next_fd = os.open(segment, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(
            "index.html", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=directory_fd,
        )
        try:
            before = os.fstat(file_fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or before.st_size < 1 or before.st_size > 1_000_000):
                raise ValueError("unsafe public profile file")
            with os.fdopen(os.dup(file_fd), "rb") as stream:
                body = stream.read(1_000_001)
            after = os.fstat(file_fd)
            if (len(body) != before.st_size or len(body) > 1_000_000
                    or after.st_dev != before.st_dev
                    or after.st_ino != before.st_ino
                    or after.st_mode != before.st_mode
                    or after.st_nlink != before.st_nlink
                    or after.st_size != before.st_size
                    or after.st_mtime_ns != before.st_mtime_ns):
                raise ValueError("public profile changed during read")
            return body
        finally:
            os.close(file_fd)
    finally:
        os.close(directory_fd)


@require_GET
def persian_author_profile(request):
    from django.conf import settings
    try:
        body = _read_author_html(settings.BASE_DIR)
    except OSError:
        # This advertised author route is temporarily unavailable, not
        # permanently removed. A 404 can cause premature search deindexing.
        response = mark_public_data_unavailable(HttpResponse(status=503))
        response["Retry-After"] = "300"
        return response
    except ValueError:
        # Corrupt/unsafe static source is an outage, not a permanent removal.
        response = mark_public_data_unavailable(HttpResponse(status=503))
        response["Retry-After"] = "300"
        return response
    return HttpResponse(body, content_type="text/html; charset=utf-8")
