"""Import official agricultural news as private editorial drafts, never publish."""

import hashlib

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Agent, NewsletterSource, NewsletterStory
from core.news_feed_reader import FEED_PUBLISHER, FEED_URL, fetch_official_news


class Command(BaseCommand):
    help = "Import non-duplicated official USDA agricultural headlines as review-only news drafts."

    def add_arguments(self, parser):
        parser.add_argument("--max-items", type=int, default=15)
        parser.add_argument("--lookback-days", type=int, default=21)

    def handle(self, *args, **options):
        agent = Agent.objects.filter(code="newsletter-world-watch", active=True).first()
        if agent is None:
            raise CommandError("Active newsletter-world-watch agent is required")
        try:
            items = fetch_official_news(
                max_items=options["max_items"], lookback_days=options["lookback_days"]
            )
        except Exception as exc:
            raise CommandError(f"Official RSS retrieval failed: {type(exc).__name__}: {exc}") from exc

        created = duplicates = 0
        for item in items:
            digest = hashlib.sha256(item.url.encode("utf-8")).hexdigest()
            fingerprint = f"official-usda-news:{digest}"
            with transaction.atomic():
                if NewsletterStory.objects.filter(fingerprint=fingerprint).exists():
                    duplicates += 1
                    continue
                source, _ = NewsletterSource.objects.get_or_create(
                    url=item.url,
                    defaults={
                        "publisher": FEED_PUBLISHER, "title": item.title,
                        "kind": "world", "retrieved_at": timezone.now(),
                        "content_hash": digest, "active": True,
                    },
                )
                # Title/metadata are a research lead, not an invented or copied article.
                summary = (
                    f"پیش‌نویس رصد خبر از {FEED_PUBLISHER}. "
                    f"عنوان منبع: {item.title}. "
                    "محتوا و ارتباط آن با کشاورزی ایران باید پیش از انتشار راستی‌آزمایی شود."
                )
                _, was_created = NewsletterStory.objects.get_or_create(
                    fingerprint=fingerprint,
                    defaults={
                        "agent": agent, "source": source, "story_type": "world",
                        "title": item.title, "slug": f"usda-news-{digest[:24]}",
                        "summary": summary,
                        "body": (
                            "این رکورد صرفاً سرنخ تحریریه از خوراک رسمی اخبار کشاورزی است. "
                            "متن کامل خبر بازنشر نشده است.\n\n"
                            f"عنوان اصلی: {item.title}\n"
                            f"منبع رسمی: {FEED_PUBLISHER}\n"
                            f"لینک خبر: {item.url}\n"
                            f"خوراک رسمی: {FEED_URL}\n"
                            f"تاریخ انتشار منبع: {item.published_at.isoformat()}\n\n"
                            "نیازمند بررسی منبع، حقیقت‌سنجی، نگارش مستقل فارسی و تأیید سردبیر."
                        ),
                        "author_name": "ایجنت پایش خبر زمرد ملل",
                        "event_date": item.published_at.date(),
                        "source_fingerprint": digest,
                        "status": "draft", "published_at": None,
                    },
                )
                created += int(was_created)
                duplicates += int(not was_created)
        self.stdout.write(self.style.SUCCESS(
            f"NEWS_AGENT=OK SOURCE=USDA_NASS REVIEWED={len(items)} "
            f"DRAFTS_CREATED={created} DUPLICATES={duplicates} PUBLISHED=0"
        ))
