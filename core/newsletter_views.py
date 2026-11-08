from django.http import Http404
from django.shortcuts import render

from .models import NewsletterPublication, NewsletterSchedule, NewsletterSource, NewsletterStory
from .editorial_signature import has_final_signature, safe_news_jsonld
from .editorial_policy import blocked_news_reason, blocked_story_reason, public_story_allowed, visible_news_stories


EDITORIAL_START = "۱۳۹۸/۰۸/۲۵"


def newsletter_home(request):
    from django.utils import timezone
    stories = visible_news_stories(
        NewsletterStory.objects.filter(status="published", published_at__lte=timezone.now()), limit=50
    )
    sources = [source for source in NewsletterSource.objects.filter(active=True)[:120]
               if not blocked_news_reason(source.title, source.publisher, source.url)][:12]
    publications = [p for p in NewsletterPublication.objects.filter(
        status="published", published_at__lte=timezone.now(),
        story__status="published", story__published_at__lte=timezone.now(),
    ).select_related("story", "story__source").order_by("-created_at")[:200]
                    if public_story_allowed(p.story)][:20]
    schedule = NewsletterSchedule.objects.filter(active=True).first()
    context = {
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
    return render(request, "core/newsletter.html", context)


def newsletter_archive(request):
    return newsletter_home(request)


def newsletter_detail(request, slug):
    from django.utils import timezone
    story = NewsletterStory.objects.select_related("source", "agent").filter(
        slug=slug, status="published", published_at__lte=timezone.now()
    ).first()
    if story is None:
        raise Http404("Newsletter story not found")
    if blocked_story_reason(story):
        raise Http404("Newsletter story unavailable under editorial policy")
    related = visible_news_stories(
        NewsletterStory.objects.filter(status="published", published_at__lte=timezone.now())
        .exclude(pk=story.pk).filter(story_type=story.story_type), limit=6
    )
    publications = story.publications.filter(
        status="published", published_at__lte=timezone.now(),
    ).order_by("channel")
    article_jsonld = safe_news_jsonld({
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": story.title,
        "description": story.summary,
        "datePublished": story.published_at.isoformat() if story.published_at else story.created_at.isoformat(),
        "dateModified": story.updated_at.isoformat(),
        "author": {"@type": "Person", "name": "مجتبی روزگار", "jobTitle": "محقق و پژوهشگر / مدیرعامل شرکت کشت و صنعت زمرد ملل", "url": "https://zomorodmelal.ir/company/executive/"},
        "publisher": {"@type": "Organization", "name": "شرکت کشت و صنعت زمرد ملل", "url": "https://zomorodmelal.ir/"},
        "image": [request.build_absolute_uri(story.image.url)] if story.image else [],
        "mainEntityOfPage": {"@type": "WebPage", "@id": f"https://zomorodmelal.ir/newsletter/{story.slug}/"}
    })
    return render(request, "core/newsletter_detail.html", {"story": story, "related": related, "publications": publications, "article_jsonld": article_jsonld, "signature_in_body": has_final_signature(story.body)})


# The public site never bypasses the editorial approval state. Drafts are visible only in admin/API workflows.
