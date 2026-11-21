"""Isolated tests: no live host, real DB, wallet, site or external service."""
import hashlib
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

from scripts import mojprop_passenger_checkout_emergency_hold_20261121 as h

BASE = (
    "import os, sys\n"
    "APP='/home/zomorod2/Saeit-mojplaywin-integrated-20261119'\n"
    "if APP not in sys.path: sys.path.insert(0, APP)\n"
    "os.chdir(APP)\n"
    "env_path=os.path.join(APP,'.env')\n"
    "if os.path.exists(env_path):\n"
    "    pass\n"
    "os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')\n"
    "from config.wsgi import application\n"
).encode()


class PassengerCheckoutHoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        public = root / 'mojplaywin.com'
        public.mkdir()
        self.wsgi = public / 'passenger_wsgi.py'
        self.wsgi.write_bytes(BASE)
        (public / 'tmp').mkdir()
        restart = public / 'tmp/restart.txt'
        restart.write_text('')
        stage = root / 'Saeit-staging'
        stage.mkdir()
        shared_env = stage / '.env'
        shared_env.write_bytes(b'MPW_MOJPROP_TRX_RELEASE_ENABLED=true\nANOTHER_APP_TOKEN=KEEP\n')
        app = root / 'Saeit-mojplaywin-integrated-20261119'
        app.mkdir()
        env = app / '.env'
        env.symlink_to(shared_env)
        self.env_file = shared_env
        self.env = env
        self.checkpoint = root / 'private-checkpoint'
        changes = (
            ('PUBLIC_ROOT', public),
            ('WSGI', self.wsgi),
            ('RESTART', restart),
            ('ENV', env),
            ('EXPECTED_SHARED_ENV', shared_env),
            ('BACKUP_DIR', self.checkpoint),
            ('PINNED_ORIGINAL_SHA256', hashlib.sha256(BASE).hexdigest()),
        )
        for key, value in changes:
            patcher = mock.patch.object(h, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_exact_candidate_changes_only_one_override_before_import(self):
        new = h.candidate(BASE)
        self.assertEqual(new.count(b'MPW_MOJPROP_TRX_RELEASE_ENABLED'), 1)
        self.assertEqual(new.replace(h.OVERRIDE.encode(), b''), BASE)
        self.assertLess(new.index(b'MPW_MOJPROP_TRX_RELEASE_ENABLED'),
                        new.index(b'from config.wsgi import application'))
        with self.assertRaises(ValueError):
            h.candidate(BASE + b'# unexpected source drift\n')

    def test_without_approval_or_zero_real_invoices_does_not_modify_anything(self):
        with self.assertRaises(PermissionError):
            h.apply(approval='', confirmed_zero_open_invoices=True)
        with self.assertRaises(PermissionError):
            h.apply(approval=h.APPROVE_APPLY, confirmed_zero_open_invoices=False)
        with mock.patch.object(h, '_read_only_actual_invoice_count', return_value=1):
            with self.assertRaises(RuntimeError):
                h.apply(approval=h.APPROVE_APPLY, confirmed_zero_open_invoices=True)
        self.assertEqual(self.wsgi.read_bytes(), BASE)
        self.assertFalse(self.checkpoint.exists())

    def test_atomic_approved_install_does_not_touch_shared_env_and_rolls_back(self):
        shared_bytes = self.env_file.read_bytes()
        with mock.patch.object(h, '_read_only_actual_invoice_count', return_value=0):
            result = h.apply(approval=h.APPROVE_APPLY,
                             confirmed_zero_open_invoices=True)
        self.assertTrue(result['hold_code_installed'])
        self.assertTrue(self.env.is_symlink())
        self.assertEqual(self.env_file.read_bytes(), shared_bytes)
        self.assertEqual(self.wsgi.read_bytes(), h.candidate(BASE))
        self.assertEqual(stat.S_IMODE((self.checkpoint / 'original-passenger_wsgi.py').stat().st_mode), 0o600)
        with self.assertRaises(PermissionError):
            h.rollback(approval='')
        with self.assertRaises(RuntimeError):
            h.apply(approval=h.APPROVE_APPLY, confirmed_zero_open_invoices=True)
        h.rollback(approval=h.APPROVE_ROLLBACK)
        self.assertEqual(self.wsgi.read_bytes(), BASE)
        self.assertEqual(self.env_file.read_bytes(), shared_bytes)


if __name__ == '__main__':
    unittest.main()
