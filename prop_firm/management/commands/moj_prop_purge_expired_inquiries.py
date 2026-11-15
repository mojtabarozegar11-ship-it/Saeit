"""Owner-supervised removal of expired opt-in Moj Prop inquiry records."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from prop_firm.models import PropInformationInquiry, PropInterestHourlyBucket


class Command(BaseCommand):
    help = "Count expired Moj Prop inquiry records. Deletion requires explicit approval."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--owner-authorized", action="store_true")

    def handle(self, *args, **options):
        cutoff = timezone.now()
        expired = PropInformationInquiry.objects.filter(expires_at__lte=cutoff)
        expired_buckets = PropInterestHourlyBucket.objects.filter(expires_at__lte=cutoff)
        count = expired.count()
        bucket_count = expired_buckets.count()
        if not options["commit"]:
            self.stdout.write(
                f"expired_inquiries={count}; expired_buckets={bucket_count}; dry_run=true"
            )
            return
        if not options["owner_authorized"]:
            raise CommandError("Explicit owner approval required for deleting inquiry data")
        with transaction.atomic():
            deleted, _ = expired.delete()
            bucket_deleted, _ = expired_buckets.delete()
        self.stdout.write(
            f"expired_inquiries_deleted={deleted}; "
            f"expired_buckets_deleted={bucket_deleted}; owner_authorized=true"
        )
