"""Opt-in stale scanner audit cleanup; NEVER fulfills, retries or refunds orders."""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from moj_commerce.models import ScannerRun
from moj_commerce.operations import ConcurrentScanner, exclusive_scanner


class Command(BaseCommand):
    help = 'Safely mark abandoned ScannerRun heartbeat records after mutex inspection.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Required for any database modification.')
        parser.add_argument('--older-than-seconds', type=int, default=900)

    def handle(self, *args, **options):
        seconds = options['older_than_seconds']
        if not 300 <= seconds <= 86400:
            raise CommandError('Recovery age outside allowed range')
        if connection.vendor != 'postgresql':
            raise CommandError('Recovery requires PostgreSQL advisory lock')
        cutoff = timezone.now() - timedelta(seconds=seconds)
        if not options['apply']:
            total = ScannerRun.objects.filter(
                status=ScannerRun.Status.RUNNING, started_at__lt=cutoff).count()
            self.stdout.write(f'MOJ_COMMERCE_STALE_DRY_RUN count={total}')
            return
        if not getattr(settings, 'MOJ_COMMERCE_RECOVERY_ENABLED', False):
            raise CommandError('Recovery writes disabled by operator policy')
        try:
            # An active scanner holding the lock is never interrupted.
            with exclusive_scanner():
                with transaction.atomic():
                    changed = ScannerRun.objects.filter(
                        status=ScannerRun.Status.RUNNING,
                        started_at__lt=cutoff).update(
                            status=ScannerRun.Status.FAILED,
                            error_code='STALE_RUN_RECOVERED',
                            finished_at=timezone.now())
                self.stdout.write(f'MOJ_COMMERCE_STALE_CLOSED count={changed}')
        except ConcurrentScanner:
            raise CommandError('Active scanner detected; no recovery performed') from None
