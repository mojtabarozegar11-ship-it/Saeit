"""Explicit, dry-run-first privacy cleanup for closed Moj Prop inquiries.

No live execution by CI or a scheduled worker. A customer request remains
untouched unless it is already closed/spam AND older than an approved horizon;
drafts, written offers, open cases and accepted work are never deleted here.
"""
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from core.models import MojPropRequest


class Command(BaseCommand):
    help = "Inspect old closed/spam leads, or delete only with explicit owner approval."

    def add_arguments(self, parser):
        parser.add_argument("--older-than-days", type=int, default=90)
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--owner-authorized", action="store_true")

    def handle(self, *args, **options):
        days=options["older_than_days"]
        if type(days) is not int or not 30<=days<=365:
            raise CommandError("closed_lead_retention_range_invalid")
        cutoff=timezone.now()-timedelta(days=days)
        old_closed=MojPropRequest.objects.filter(
            status__in=("closed","spam"),
            created_at__lte=cutoff,
        )
        records=old_closed.count()
        if not options["commit"]:
            self.stdout.write(
                f"closed_old_mojprop_leads={records}; retention_days={days}; "
                "dry_run=true; buyer_identity_redacted=true"
            )
            return
        if not options["owner_authorized"]:
            raise CommandError("owner_approval_required_for_closed_lead_deletion")
        with transaction.atomic():
            # Re-evaluate guard at commit time to avoid deleting an inquiry that
            # is now under review or a recently delivered commercial order.
            deleted,_=MojPropRequest.objects.filter(
                status__in=("closed","spam"),
                created_at__lte=cutoff,
            ).delete()
        self.stdout.write(
            f"closed_old_mojprop_leads_deleted={deleted}; "
            "owner_authorized=true; buyer_identity_redacted=true"
        )
