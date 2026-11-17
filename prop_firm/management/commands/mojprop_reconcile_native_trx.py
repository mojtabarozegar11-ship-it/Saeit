"""Run private direct-TRX payment watcher in a controlled server scheduler.

Usage: python manage.py mojprop_reconcile_native_trx
No cron entry or production host changes are performed by this source file.
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from prop_firm.plan1_v141_native_checkout import CheckoutRejected
from prop_firm.plan1_v141_native_watcher import reconcile_pending_invoices


class Command(BaseCommand):
    help = "Reconcile and deliver eligible foreign MOJ-PROP-01 native TRX orders"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Discover candidates, never deliver or write")

    def handle(self, *args, **options):
        if getattr(settings, "MOJPROP_TRX_AUTORECONCILE_ENABLED", False) is not True:
            raise CommandError("Audited TRON reconciliation service is disabled")
        if connection.vendor != "mysql":
            raise CommandError("MySQL/MariaDB advisory lock is mandatory")
        # Global advisory lock is connection-scoped across all workers.
        lock_name = "mojprop:native:trx:wallet:owner"
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT GET_LOCK(%s, 0)", [lock_name])
                acquired = cursor.fetchone()
            if not acquired or acquired[0] != 1:
                raise CommandError("Another TRX reconciliation process holds the lock")
            try:
                result = reconcile_pending_invoices(dry_run=options["dry_run"])
                # Do not log account addresses, buyer details or secret keys.
                self.stdout.write(json.dumps(result, sort_keys=True))
            except CheckoutRejected as exc:
                raise CommandError(str(exc)) from exc
        finally:
            # Not obtaining the lock must never release another process' lock.
            if 'acquired' in locals() and acquired and acquired[0] == 1:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", [lock_name])
