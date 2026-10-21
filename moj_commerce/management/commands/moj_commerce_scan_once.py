"""Owner-approved opt-in scanner run. Never scheduled/deployed by CI."""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection
from moj_commerce.models import ScannerRun
from moj_commerce.operations import exclusive_scanner, ConcurrentScanner, record_scanner_completion
from moj_commerce.scan_purchases import scan_purchases_once, ScanUnavailable


class Command(BaseCommand):
    help='Bounded TRX scanner. Requires PostgreSQL or MySQL/MariaDB with verified locks and explicit operator settings.'

    def handle(self, *args, **options):
        if connection.vendor not in ('postgresql', 'mysql'):
            raise CommandError('TRX financial scanning requires PostgreSQL or MySQL/MariaDB')
        # Do not create a misleading "running" record on an unconfigured system.
        if not getattr(settings,'MOJ_COMMERCE_SCANNER_ENABLED',False):
            raise CommandError('TRX scanner is disabled by operator policy')
        checker=getattr(settings,'MOJ_COMMERCE_FINALIZED_TRON_CHECKER',None)
        secret=getattr(settings,'MOJ_COMMERCE_FULFILL_SECRET','')
        if not callable(checker) or not isinstance(secret,str) or len(secret)<32:
            raise CommandError('TRX scanner lacks trusted finalized proof or store secret')
        try:
            with exclusive_scanner():
                run=ScannerRun.objects.create()
                try:
                    data=scan_purchases_once()
                    record_scanner_completion(run,data)
                except (Exception,):
                    # Do not write error text: it may contain addresses, tokens or RPC data.
                    record_scanner_completion(run,failed=True)
                    raise CommandError('TRX scan failed; inspect restricted operational incident records') from None
                # Only whitelisted counters, never raw addresses or tx IDs.
                self.stdout.write('MOJ_COMMERCE_SCAN_COUNTS '+ ' '.join(
                    f'{key}={getattr(run,key)}' for key in
                    ('scanned','fulfilled','failures','discrepancies','manual_review')))
        except ConcurrentScanner as exc:
            raise CommandError(str(exc)) from exc