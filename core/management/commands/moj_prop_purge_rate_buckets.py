"""Durable, operator-mediated cleanup for canonical Moj Prop abuse counters.

Never purges customer inquiries or their consent records. Default is read-only.
Even short-lived HMAC counter rows require a separate owner-authorized write.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from core.models import MojPropRateBucket


class Command(BaseCommand):
    help = "Inspect expired Moj Prop intake quota rows; delete only with owner approval."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--owner-authorized", action="store_true")

    def handle(self, *args, **options):
        expired = MojPropRateBucket.objects.filter(expires_at__lte=timezone.now())
        count = expired.count()
        if not options["commit"]:
            self.stdout.write(f"moj_prop_expired_quota_rows={count}; dry_run=true")
            return
        if not options["owner_authorized"]:
            raise CommandError("Explicit owner approval is required for retention deletion")
        with transaction.atomic():
            rows_deleted, _ = expired.delete()
        self.stdout.write(
            f"moj_prop_expired_quota_rows_deleted={rows_deleted}; owner_authorized=true"
        )
