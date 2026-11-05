"""Process actual owner newsletter submissions; never invent or publish content.

Invoke from an independently configured cPanel/VPS scheduler after deployment.
Each run handles at most 20 real submissions and prints a machine-readable
receipt, without making external requests or relying on GitHub Actions.
"""

import json

from django.core.management.base import BaseCommand, CommandError

from core.newsletter_engine import process_submission
from core.newsletter_models import NewsletterSubmission


class Command(BaseCommand):
    help = "Process up to 20 queued owner submissions into approval-gated drafts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=20,
            help="Maximum queued submissions handled in this run (1-20).",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 20:
            raise CommandError("--limit must be between 1 and 20")

        pending = list(
            NewsletterSubmission.objects.filter(status="queued")
            .order_by("created_at", "pk")[:limit]
        )
        counts = {
            "inspected": len(pending),
            "drafted": 0,
            "held": 0,
            "rejected": 0,
            "claimed_elsewhere": 0,
            "errors": 0,
            "external_messages_sent": 0,
            "publicly_published": 0,
        }
        error_types = {}

        for item in pending:
            try:
                story = process_submission(item)
                item.refresh_from_db(fields=["status", "generated_story"])
            except Exception as exc:
                # The engine's atomic transaction rolls back the claim, so the
                # item remains queued and is recoverable on the next run.
                counts["errors"] += 1
                error_types[type(exc).__name__] = error_types.get(type(exc).__name__, 0) + 1
                continue

            if item.status == "drafted" and story is not None:
                counts["drafted"] += 1
            elif item.status == "rejected":
                counts["rejected"] += 1
            elif item.status == "queued":
                counts["held"] += 1
            else:
                counts["claimed_elsewhere"] += 1

        self.stdout.write(json.dumps({
            "command": "newsletter_process_queue",
            "result": counts,
            "remaining_queued": NewsletterSubmission.objects.filter(status="queued").count(),
            "preexisting_inflight": NewsletterSubmission.objects.filter(status="processing").count(),
            "error_types": error_types,
            "publication_gate": "configured_schedule_or_default_hold",
        }, sort_keys=True))
