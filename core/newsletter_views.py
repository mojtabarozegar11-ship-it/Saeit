import json
from django.http import Http404, HttpResponse
from django.shortcuts import render

from .models import Agent, NewsletterPublication, NewsletterSchedule, NewsletterSource, NewsletterStory
from .public_catalog_guard import missing_public_tables, mark_public_data_unavailable


EDITORIAL_START = "۱۳۹۸/۰۸/۲۵"


def safe_json_ld(payload):
    """Escape HTML-significant characters inside JSON-LD script content.

    The template embeds this JSON as |safe inside <script type=application/ld+json>.
    Raw </script> in an editorial title must never terminate that script.
    """
    return (json.dumps(payload, ensure_ascii=False)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026"))


def verified_story_author(story):
    """Attribute structured data to the stored editorial byline, not a fixed CEO.

    A blank byline is attributed to the publisher organization; never invent a
    person's credentials, role or profile URL for unrelated articles.
    """
    byline = (story.author_name or "").strip()
    if byline:
        return {"@type": "Person", "name": byline}
    return {"@type": "Organization", "name": "شرکت کشت و صنعت زمرد ملل"}


def newsletter_home(request):
    from django.utils import timezone
    catalog_unavailable = missing_public_tables(
        NewsletterStory, NewsletterSource, NewsletterPublication, NewsletterSchedule, Agent
    )
    if catalog_unavailable:
        stories, sources, publications, schedule = [], [], [], None
    else:
        stories = NewsletterStory.objects.filter(
            status="published", published_at__lte=timezone.now()
        ).select_related("source", "agent")[:50]
        sources = NewsletterSource.objects.filter(active=True)[:12]
        publications = (NewsletterPublication.objects.filter(
            story__status="published", story__published_at__lte=timezone.now(),
            status="published", published_at__lte=timezone.now(),
        ).select_related("story").order_by("-created_at")[:20])
        schedule = NewsletterSchedule.objects.filter(active=True).first()
    context = {
        "catalog_temporarily_unavailable": catalog_unavailable,
        "stories": stories,
        "sources": sources,
        "publications": publications,
        "schedule": schedule,
        "editorial_start": EDITORIAL_START,
        "agent_specs": [
            ("01", "ایجنت تخصصی خبرنامه", "مدیریت زنجیره تولید، کنترل تکرار، بررسی منبع، سئو و آماده‌سازی انتشار."),
            ("02", "ایجنت اخبار فعالیت شرکت", "روزانه ۴ خبر مستند از فعالیت‌ها، پژوهش‌ها و خروجی‌های واقعی شرکت؛ بدون ساختن رویداد غیرواقعی."),
            ("03", "ایجنت رصد اخبار جهان", "گردآوری و راستی‌آزمایی اخبار معتبر جهانی در حوزه‌های مرتبط با فعالیت شرکت و تبدیل آن به گزارش فارسی با ذکر منبع."),
            ("04", "ایجنت گزارش عملکرد واحدها", "روزانه ۴ گزارش مستقل از داده‌های ثبت‌شده واحدها، پروژه‌ها، پژوهش‌ها و مسیرهای توسعه شرکت."),
        ],
        "social_channels": [
            "سایت شرکت", "Instagram", "Facebook", "YouTube", "X", "LinkedIn",
            "Telegram", "Eitaa", "Rubika", "Bale",
        ],
    }
    response = render(request, "core/newsletter.html", context)
    return mark_public_data_unavailable(response) if catalog_unavailable else response


def newsletter_archive(request):
    return newsletter_home(request)


def newsletter_detail(request, slug):
    # Article data cannot be reconstructed from a missing schema. Return a
    # truthful, temporary failure instead of an OperationalError/false 404.
    if missing_public_tables(NewsletterStory, NewsletterSource, NewsletterPublication, Agent):
        response = HttpResponse(
            '<!doctype html><html lang="fa" dir="rtl"><head>'
            '<meta charset="utf-8"><title>خبرنامه موقتاً در دسترس نیست</title>'
            '</head><body><main><h1>خبرنامه موقتاً در دسترس نیست</h1>'
            '<p role="status">بازیابی اطلاعات این خبر در حال پیگیری است؛ '
            'این وضعیت به معنای حذف مطلب نیست.</p>'
            '<p><a href="/newsletter/">بازگشت به خبرنامه</a></p>'
            '</main></body></html>',
            status=503,
            content_type="text/html; charset=utf-8",
        )
        response["Retry-After"] = "300"
        return mark_public_data_unavailable(response)
    from django.utils import timezone
    story = NewsletterStory.objects.select_related("source", "agent").filter(
        slug=slug, status="published", published_at__lte=timezone.now()
    ).first()
    if story is None:
        raise Http404("Newsletter story not found")
    # A future-dated story may be editorially marked published but remains
    # embargoed. Related links must obey the same visibility gate as detail.
    related = (NewsletterStory.objects.filter(
        status="published", published_at__lte=timezone.now(),
        story_type=story.story_type,
    ).exclude(pk=story.pk).order_by("-published_at")[:6])
    # Public article pages must not expose queued, failed or blocked
    # distribution records (including internal error/status metadata).
    publications = story.publications.filter(
        status="published", published_at__lte=timezone.now()
    ).order_by("channel")
    article_jsonld = safe_json_ld({
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": story.title,
        "description": story.summary,
        "datePublished": story.published_at.isoformat() if story.published_at else story.created_at.isoformat(),
        "dateModified": story.updated_at.isoformat(),
        "author": verified_story_author(story),
        "publisher": {"@type": "Organization", "name": "شرکت کشت و صنعت زمرد ملل", "url": "https://zomorodmelal.ir/"},
        "image": [request.build_absolute_uri(story.image.url)] if story.image else [],
        "mainEntityOfPage": {"@type": "WebPage", "@id": f"https://zomorodmelal.ir/newsletter/{story.slug}/"}
    })
    return render(request, "core/newsletter_detail.html", {"story": story, "related": related, "publications": publications, "article_jsonld": article_jsonld})


# The public site never bypasses the editorial approval state. Drafts are visible only in admin/API workflows.
