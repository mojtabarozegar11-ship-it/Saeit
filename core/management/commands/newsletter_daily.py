from django.core.management.base import BaseCommand
from django.utils import timezone

from core.newsletter_engine import daily_quota_snapshot


class Command(BaseCommand):
    help = "Validate the daily newsletter production quota without inventing or publishing content."

    def handle(self, *args, **options):
        snapshot = daily_quota_snapshot(timezone.localdate())
        if not snapshot.get("configured"):
            self.stderr.write("Newsletter schedule is not configured.")
            return
        self.stdout.write(f"Newsletter date: {snapshot['date']}")
        self.stdout.write(f"Publication approval required: {snapshot['approval_required']}")
        for kind, item in snapshot["counts"].items():
            self.stdout.write(f"{kind}: published={item['published']} target={item['target']} remaining={item['remaining']}")
        self.stdout.write("No story is fabricated when the source/activity data is missing.")
