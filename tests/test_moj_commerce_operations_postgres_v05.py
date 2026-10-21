"""PostgreSQL session-level financial scanner mutex validation."""
from concurrent.futures import ThreadPoolExecutor
from django.db import connection, close_old_connections
from django.test import TransactionTestCase, override_settings
from django.core.management import call_command, CommandError
from moj_commerce.models import ScannerRun
from moj_commerce.operations import exclusive_scanner, ConcurrentScanner
from unittest.mock import patch
from io import StringIO


def fake_verifier(*a,**kw):
    raise AssertionError('A real chain lookup is forbidden in CI')


class PostgreSQLScannerOpsTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor!='postgresql':
            self.skipTest('No finance-lock fallback on SQLite')

    def _try_other_session(self):
        close_old_connections()
        try:
            with exclusive_scanner():
                return 'unexpected_acquisition'
        except ConcurrentScanner:
            return 'blocked'
        finally:
            close_old_connections()

    def test_only_one_worker_holds_advisory_lock(self):
        with exclusive_scanner():
            with ThreadPoolExecutor(max_workers=1) as pool:
                state=pool.submit(self._try_other_session).result(timeout=10)
            self.assertEqual(state,'blocked')
        self.assertEqual(self._try_other_session(),'unexpected_acquisition')

    @override_settings(MOJ_COMMERCE_SCANNER_ENABLED=True,
                       MOJ_COMMERCE_FINALIZED_TRON_CHECKER=fake_verifier,
                       MOJ_COMMERCE_FULFILL_SECRET='operator-only-'+'X'*40)
    def test_command_records_sanitized_success_and_failure(self):
        stats={'scanned':4,'fulfilled':1,'underpaid':1,'overpaid':0,
               'manual_review':1,'failures':0}
        with patch('moj_commerce.management.commands.moj_commerce_scan_once.scan_purchases_once',return_value=stats):
            stream=StringIO();call_command('moj_commerce_scan_once',stdout=stream)
            self.assertIn('scanned=4',stream.getvalue())
        recent=ScannerRun.objects.latest('pk')
        self.assertEqual((recent.status,recent.fulfilled,recent.discrepancies),('ok',1,1))
        with patch('moj_commerce.management.commands.moj_commerce_scan_once.scan_purchases_once',side_effect=RuntimeError('VERY SECRET CUSTOMER DATA')):
            try:
                call_command('moj_commerce_scan_once',stdout=StringIO())
            except CommandError as e:
                self.assertNotIn('VERY SECRET',str(e))
            else:
                self.fail('Scanner error must not be reported as success')
        recent=ScannerRun.objects.latest('pk')
        self.assertEqual(recent.status,'failed')
        self.assertEqual(recent.error_code,'SCAN_FAILED')
        self.assertNotIn('VERY SECRET',recent.error_code)

    @override_settings(MOJ_COMMERCE_SCANNER_ENABLED=False)
    def test_disabled_command_never_records_fake_run(self):
        with self.assertRaises(CommandError):
            call_command('moj_commerce_scan_once',stdout=StringIO())
        self.assertFalse(ScannerRun.objects.exists())