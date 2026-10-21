"""Conservative self-healer for missing purchase scan states, opt-in only.

It can only restore an unexpired invoice's scan queue entry. It never sets
payment status, creates entitlements or triggers blockchain reads.
"""
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from moj_commerce.models import Purchase, PurchaseScanState
from moj_commerce.operations import ConcurrentScanner, exclusive_scanner
from moj_commerce.self_repair import scan_repair_eligibility


class Command(BaseCommand):
    help = 'Audit/restore missing scanner schedules for verified, unexpired orders.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Explicit approval for a bounded schedule-only write.')
        parser.add_argument('--limit', type=int, default=25)

    def handle(self, *args, **options):
        limit = options['limit']
        if type(limit) is not int or not 1 <= limit <= 25:
            raise CommandError('Repair limit must be between 1 and 25')
        if connection.vendor != 'postgresql':
            raise CommandError('Self-repair requires PostgreSQL advisory locking')
        if options['apply'] and not getattr(settings, 'MOJ_COMMERCE_SELF_REPAIR_ENABLED', False):
            raise CommandError('Self-repair disabled by operator policy')
        try:
            # Same global mutex as the scanner: never touch its schedule mid-scan.
            with exclusive_scanner():
                with transaction.atomic():
                    now = timezone.now()
                    # Newest open invoices first; never revive expired payments.
                    missing = Purchase.objects.filter(
                        status=Purchase.Status.PENDING, scan_state__isnull=True,
                    ).select_related('merchant', 'product', 'destination').order_by(
                        '-created_at', '-pk')
                    total_missing = missing.count()
                    # Lock the purchase itself, not the nullable outer-joined scan_state.
                    candidates = list(missing.select_for_update(of=('self',))[:limit])
                    outcomes = Counter()
                    for purchase in candidates:
                        reason = scan_repair_eligibility(purchase, now=now)
                        outcomes[reason] += 1
                        if reason != 'eligible' or not options['apply']:
                            continue
                        # OneToOne uniqueness is a second race-safety boundary.
                        _, created = PurchaseScanState.objects.get_or_create(
                            purchase_id=purchase.pk,
                            defaults={'next_scan_ms': int(now.timestamp() * 1000)},
                        )
                        outcomes['repaired' if created else 'already_present'] += 1
                    mode = 'APPLIED' if options['apply'] else 'DRY_RUN'
                    summary = ' '.join(f'{key}={outcomes[key]}' for key in sorted(outcomes))
                    self.stdout.write(
                        f'MOJ_COMMERCE_SELF_REPAIR_{mode} missing={total_missing} '
                        f'inspected={len(candidates)} limit={limit} {summary}'
                    )
        except ConcurrentScanner:
            raise CommandError('Active scanner detected; no repair performed') from None
