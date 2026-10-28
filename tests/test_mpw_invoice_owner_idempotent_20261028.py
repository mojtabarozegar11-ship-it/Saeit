"""Offline, non-transactional guards for the existing invoice recovery release.

No database, payment, HTTP request, or production file is used.
"""
import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mpw_invoice_owner_safe_recovery_20261026.py"
SPEC = importlib.util.spec_from_file_location("mpw_invoice_owner_release_test", SCRIPT)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class InvoiceOwnerReleaseSafetyTests(unittest.TestCase):
    def test_prepare_is_read_only_and_compiles_both_patches(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            login = root / "customer_auth.py"
            invoice = root / "mpw_trx_commercial_web.py"
            login.write_text("class CustomerLogin:\n" + release.LOGIN_OLD, encoding="utf-8")
            invoice.write_text("def _show_invoice(request, invoice_id):\n"
                               + release.INVOICE_OLD, encoding="utf-8")
            originals = {login: login.read_bytes(), invoice: invoice.read_bytes()}
            with patch.object(release, "APP", root), patch.dict(
                release.TARGETS, {"login": login, "invoice": invoice}, clear=True
            ):
                changes = release.prepare()
                self.assertEqual(set(changes), {"login", "invoice"})
                for key, (target, old, new) in changes.items():
                    self.assertEqual(old, originals[target])
                    self.assertNotEqual(new, old)
                    compile(new, str(target), "exec")
                self.assertEqual(login.read_bytes(), originals[login])
                self.assertEqual(invoice.read_bytes(), originals[invoice])

    def test_already_applied_sources_are_noop(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            login = root / "customer_auth.py"
            invoice = root / "mpw_trx_commercial_web.py"
            login.write_text("class CustomerLogin:\n" + release.LOGIN_NEW, encoding="utf-8")
            invoice.write_text("def _show_invoice(request, invoice_id):\n"
                               + release.INVOICE_NEW, encoding="utf-8")
            with patch.object(release, "APP", root), patch.dict(
                release.TARGETS, {"login": login, "invoice": invoice}, clear=True
            ):
                self.assertEqual(release.prepare(), {})

    def test_repeated_apply_validates_but_does_not_backup_or_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out = io.StringIO()
            with patch.object(release, "APP", root), \
                 patch.object(release, "prepare", return_value={}), \
                 patch.object(release, "validate") as validate, \
                 patch.object(release, "reload_passenger") as restart, \
                 patch.object(sys, "argv", ["release", "apply"]), \
                 redirect_stdout(out):
                release.main()
            validate.assert_called_once_with()
            restart.assert_not_called()
            self.assertFalse((root / ".release-backups").exists())
            self.assertIn("ALREADY_APPLIED_VERIFIED", out.getvalue())

    def test_rejects_symlinked_source_without_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "original.py"
            original.write_text("safe", encoding="utf-8")
            alias = root / "alias.py"
            alias.symlink_to(original)
            with patch.object(release, "APP", root):
                with self.assertRaises(RuntimeError):
                    release.safe_target(alias)
            self.assertEqual(original.read_text(encoding="utf-8"), "safe")


if __name__ == "__main__":
    unittest.main()
