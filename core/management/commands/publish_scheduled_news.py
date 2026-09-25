from django.core.management.base import BaseCommand
from django.utils import timezone

from core.newsletter_models import NewsletterStory


class Command(BaseCommand):
    help = "Publish approved/scheduled newsletter stories whose requested date has arrived."

    def handle(self, *args, **options):
        now = timezone.now()
        qs = NewsletterStory.objects.filter(status="scheduled", published_at__isnull=False, published_at__lte=now)
        count = qs.update(status="published")
        self.stdout.write(self.style.SUCCESS(f"Published {count} scheduled newsletter stories."))
