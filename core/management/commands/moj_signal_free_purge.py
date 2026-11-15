"""Optional privacy clean-up of unconfirmed registrations only.

Deletes only aged unconfirmed records. Do NOT delete unsubscribe suppression,
confirmed opt-in records, customer orders, or payment evidence.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.signal_free_models import MojSignalFreeSubscription


class Command(BaseCommand):
    help = "Purge pending opt-in requests over 30 days old; leave suppression intact."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Actually remove only expired pending records.")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=30)
        qs = MojSignalFreeSubscription.objects.filter(
            status="pending", created_at__lt=cutoff,
        )
        count = qs.count()
        if options["apply"]:
            qs.delete()
        self.stdout.write(
            f"free_pending_older_30d={count} removed={count if options['apply'] else 0} "
            f"confirmed_or_unsubscribed_touched=0"
        )
