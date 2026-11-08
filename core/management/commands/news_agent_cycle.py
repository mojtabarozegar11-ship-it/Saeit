"""Import official agricultural news as private editorial drafts, never publish."""

import hashlib

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Agent, NewsletterSource, NewsletterStory
from core.news_feed_reader import OFFICIAL_FEEDS, editorial_identity, fetch_official_news
from core.editorial_signature import ensure_signed


class Command(BaseCommand):
    help = "Import official USDA and FAO news headlines as review-only editorial drafts."

    def add_arguments(self, parser):
        parser.add_argument("--max-items", type=int, default=15)
        parser.add_argument("--lookback-days", type=int, default=21)

    def handle(self, *args, **options):
        agent = Agent.objects.filter(code="newsletter-world-watch", active=True).first()
        if agent is None:
            raise CommandError("Active newsletter-world-watch agent is required")
        try:
            report = fetch_official_news(
                max_items=options["max_items"], lookback_days=options["lookback_days"]
            )
        except Exception as exc:
            raise CommandError(f"Official RSS retrieval failed: {type(exc).__name__}: {exc}") from exc

        created = duplicates = 0
        for item in report.items:
            digest = hashlib.sha256(item.url.encode("utf-8")).hexdigest()
            fingerprint, slug = editorial_identity(item)
            with transaction.atomic():
                if NewsletterStory.objects.filter(fingerprint=fingerprint).exists():
                    duplicates += 1
                    continue
                source, _ = NewsletterSource.objects.get_or_create(
                    url=item.url,
                    defaults={
                        "publisher": item.publisher, "title": item.title,
                        "kind": "world", "retrieved_at": timezone.now(),
                        "content_hash": digest, "active": True,
                    },
                )
                # Title/metadata are a research lead, not an invented or copied article.
                summary = (
                    f"پیش‌نویس رصد خبر از {item.publisher}. "
                    f"عنوان منبع: {item.title}. "
                    "محتوا و ارتباط آن با کشاورزی ایران باید پیش از انتشار راستی‌آزمایی شود."
                )
                _, was_created = NewsletterStory.objects.get_or_create(
                    fingerprint=fingerprint,
                    defaults={
                        "agent": agent, "source": source, "story_type": "world",
                        "title": item.title, "slug": slug,
                        "summary": summary,
                        "body": ensure_signed(
                            "این رکورد صرفاً سرنخ تحریریه از خوراک رسمی اخبار کشاورزی است. "
                            "متن کامل خبر بازنشر نشده است.\n\n"
                            f"عنوان اصلی: {item.title}\n"
                            f"منبع رسمی: {item.publisher}\n"
                            f"لینک خبر: {item.url}\n"
                            f"خوراک رسمی: {item.feed_url}\n"
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
            f"NEWS_AGENT=OK OFFICIAL_FEEDS={len(OFFICIAL_FEEDS)} "
            f"FEEDS_OK={report.feeds_ok} FEEDS_FAILED={len(report.feed_errors)} "
            f"REVIEWED={len(report.items)} "
            f"DRAFTS_CREATED={created} DUPLICATES={duplicates} PUBLISHED=0"
        ))
        for error in report.feed_errors:
            self.stderr.write(f"NEWS_AGENT_FEED_WARNING={error}")
