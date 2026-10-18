"""Prune old MojPlayWin-only rate-limit records in isolated deployment."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.mojplaywin_crypto_models import MojCryptoThrottle


class Command(BaseCommand):
    help = "Remove MojPlayWin crypto throttle counters older than two days."

    def handle(self, *args, **options):
        threshold = int(timezone.now().timestamp()) // 60 - 2 * 24 * 60
        # Bucket sizes are 60s or 600s. Convert each to a common age comparison.
        old = MojCryptoThrottle.objects.filter(action__startswith="min-", bucket__lt=threshold)
        count = old.count()
        old.delete()
        hour_threshold = int(timezone.now().timestamp()) // 600 - 2 * 24 * 6
        old10 = MojCryptoThrottle.objects.filter(action__startswith="ten-", bucket__lt=hour_threshold)
        count += old10.count()
        old10.delete()
        self.stdout.write(f"Pruned {count} expired throttle entries.")
