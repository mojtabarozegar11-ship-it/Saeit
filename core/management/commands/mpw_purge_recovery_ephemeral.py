"""Prune expired recovery secrets and rate buckets; keep immutable order claims."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import GuestRecoveryRate, GuestRecoveryToken


class Command(BaseCommand):
    help = "Remove expired MojPlayWin recovery tokens and throttle buckets only"

    def handle(self, *args, **options):
        now = timezone.now()
        with transaction.atomic():
            tokens, _ = GuestRecoveryToken.objects.filter(
                expires_at__lt=now - timedelta(days=1)
            ).delete()
            buckets, _ = GuestRecoveryRate.objects.filter(
                expires_at__lt=now - timedelta(days=1)
            ).delete()
        self.stdout.write(
            "MPW_RECOVERY_EPHEMERAL_PURGED=" + str(tokens) +
            ";RATE_BUCKETS_PURGED=" + str(buckets) +
            ";ORDER_EMAIL_CLAIMS_REMOVED=0"
        )
