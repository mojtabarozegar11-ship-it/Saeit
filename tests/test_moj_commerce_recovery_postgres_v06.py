"""Real PostgreSQL mutex protection for opt-in operational audit recovery."""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from moj_commerce.models import ScannerRun
from moj_commerce.operations import exclusive_scanner


class StaleRunRecoveryTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL-only audit recovery')

    def test_dry_run_disabled_gate_then_safe_apply(self):
        stale = ScannerRun.objects.create(
            started_at=timezone.now()-timedelta(minutes=40))
        recent = ScannerRun.objects.create()
        call_command('moj_commerce_recover_stale', stdout=StringIO())
        stale.refresh_from_db()
        self.assertEqual(stale.status, ScannerRun.Status.RUNNING)
        with self.assertRaises(CommandError):
            call_command('moj_commerce_recover_stale', apply=True, stdout=StringIO())
        with override_settings(MOJ_COMMERCE_RECOVERY_ENABLED=True):
            output=StringIO()
            call_command('moj_commerce_recover_stale', apply=True, stdout=output)
        stale.refresh_from_db()
        recent.refresh_from_db()
        self.assertEqual(stale.status, ScannerRun.Status.FAILED)
        self.assertEqual(stale.error_code, 'STALE_RUN_RECOVERED')
        self.assertEqual(recent.status, ScannerRun.Status.RUNNING)
        self.assertIn('count=1', output.getvalue())

    @override_settings(MOJ_COMMERCE_RECOVERY_ENABLED=True)
    def test_no_metadata_recovery_if_an_active_scanner_holds_mutex(self):
        stale = ScannerRun.objects.create(
            started_at=timezone.now()-timedelta(minutes=40))
        with exclusive_scanner():
            with self.assertRaises(CommandError):
                # A second database session is needed to represent another process.
                with patch('moj_commerce.management.commands.moj_commerce_recover_stale.exclusive_scanner',
                           side_effect=__import__('moj_commerce.operations', fromlist=['ConcurrentScanner']).ConcurrentScanner):
                    call_command('moj_commerce_recover_stale', apply=True, stdout=StringIO())
        stale.refresh_from_db()
        self.assertEqual(stale.status, ScannerRun.Status.RUNNING)
