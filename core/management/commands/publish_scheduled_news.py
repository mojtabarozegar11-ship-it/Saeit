from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import NewsletterSchedule
from core.newsletter_models import NewsletterStory


class Command(BaseCommand):
    help = "Publish due newsletter stories, respecting the configured owner-approval gate."

    def handle(self, *args, **options):
        now = timezone.now()
        schedule = NewsletterSchedule.objects.filter(active=True).first()
        approval_required = bool(schedule and schedule.publication_requires_approval)
        allowed_status = "approved" if approval_required else "scheduled"
        qs = NewsletterStory.objects.filter(
            status=allowed_status, published_at__isnull=False, published_at__lte=now
        )
        count = qs.update(status="published")
        self.stdout.write(self.style.SUCCESS(
            f"Published {count} due newsletter stories (approval_required={approval_required})."
        ))
