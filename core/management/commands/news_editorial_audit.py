"""Read-only safety audit; never change stories or distribution records."""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from core.editorial_audit import summarize_editorial_stories
from core.models import BlogPublication, NewsletterPublication, NewsletterStory


class Command(BaseCommand):
    help = "Read-only audit: political/Israel news in legacy stories and distribution queues."

    def add_arguments(self, parser):
        parser.add_argument("--max-records", type=int, default=10000)
        parser.add_argument("--strict", action="store_true", help="Fail if prohibited stories are published or scheduled")

    def handle(self, *args, **options):
        max_records = options["max_records"]
        if max_records < 1 or max_records > 50000:
            raise CommandError("max-records must be between 1 and 50000")

        queryset = NewsletterStory.objects.select_related("source").order_by("pk")
        total = queryset.count()
        summary = summarize_editorial_stories(queryset[:max_records])
        blocked_ids = summary.pop("blocked_ids")
        summary["database_total"] = total
        summary["partial_scan"] = total > summary["scanned"]
        summary["publication_statuses"] = {}
        if blocked_ids:
            for label, model in (
                ("newsletter", NewsletterPublication), ("blog", BlogPublication),
            ):
                summary["publication_statuses"][label] = {
                    row["status"]: row["count"]
                    for row in model.objects.filter(story_id__in=blocked_ids)
                    .values("status").annotate(count=Count("pk"))
                }
        summary["unsafe_published_distributions"] = sum(
            statuses.get("published", 0)
            for statuses in summary["publication_statuses"].values()
        )
        self.stdout.write(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        if options["strict"] and (
            summary["partial_scan"] or summary["public_or_scheduled_blocked_total"]
            or summary["unsafe_published_distributions"]
        ):
            raise CommandError("Editorial policy audit did not pass; no records were changed")
