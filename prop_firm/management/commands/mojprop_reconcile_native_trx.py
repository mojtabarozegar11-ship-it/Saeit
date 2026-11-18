"""Scheduled private TRX reconciliation; SQLite and MariaDB exclusive locks.

Never called from a buyer request. No TRON broadcast, no wallet private key.
The invoking operator schedules the job outside this source module.
"""
import fcntl
import json
import os
import stat
from pathlib import Path
from contextlib import contextmanager

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from prop_firm.plan1_v141_native_checkout import CheckoutRejected
from prop_firm.plan1_v141_native_watcher import reconcile_pending_invoices


@contextmanager
def exclusive_reconcile_lock():
    """Cross-process exclusive coordinator; NEVER rely on SQLite row locks.

    MySQL/MariaDB: connection-owned database named lock.
    Standalone SQLite: require Django BEGIN IMMEDIATE transaction support,
    single owner-owned private ledger, and nonblocking kernel file lock.
    Closing FD releases flock automatically even after an exception.
    """
    if connection.vendor == "mysql":
        lock_name = "mojprop:native:trx:wallet:owner"
        acquired = False
        with connection.cursor() as cur:
            cur.execute("SELECT GET_LOCK(%s, 0)", [lock_name])
            acquired = cur.fetchone() == (1,)
        if not acquired:
            raise CommandError("Another TRX reconciliation job owns the MariaDB lock")
        try:
            yield
        finally:
            with connection.cursor() as cur:
                cur.execute("SELECT RELEASE_LOCK(%s)", [lock_name])
    elif (connection.vendor == "sqlite"
          and getattr(connection, "transaction_mode", None) == "IMMEDIATE"):
        db = Path(settings.DATABASES["default"]["NAME"])
        if not db.is_absolute() or db.is_symlink() or not db.is_file():
            raise CommandError("Standalone private ledger is missing")
        folder = db.parent
        if (folder.is_symlink() or not folder.is_dir()
                or folder.stat().st_uid != os.getuid()
                or stat.S_IMODE(folder.stat().st_mode) != 0o700):
            raise CommandError("Private merchant ledger folder has unsafe owner or mode")
        lock_path = folder / "mojprop-trx-reconcile.lock"
        if lock_path.is_symlink():
            raise CommandError("Unsafe symlink lock target")
        descriptor = os.open(
            str(lock_path), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            metadata = os.fstat(descriptor)
            if (not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_uid != os.getuid()
                    or stat.S_IMODE(metadata.st_mode) != 0o600
                    or metadata.st_nlink != 1):
                raise CommandError("SQLite reconciliation lock file unsafe")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise CommandError("Another SQLite TRX reconciliation job runs") from exc
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
    else:
        raise CommandError("Only serialized MySQL or SQLite IMMEDIATE supported")


class Command(BaseCommand):
    help = "Reconcile and deliver eligible foreign MOJ-PROP-01 native TRX orders"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Discover candidates, never deliver or write")

    def handle(self, *args, **options):
        if getattr(settings, "MOJPROP_TRX_AUTORECONCILE_ENABLED", False) is not True:
            raise CommandError("Audited TRON reconciliation service is disabled")
        with exclusive_reconcile_lock():
            try:
                result = reconcile_pending_invoices(dry_run=options["dry_run"])
            except CheckoutRejected as exc:
                raise CommandError(str(exc)) from exc
            # Do not log account addresses, buyer details or wallet secrets.
            self.stdout.write(json.dumps(result, sort_keys=True))
