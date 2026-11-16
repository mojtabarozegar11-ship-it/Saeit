"""Offline synthetic tests for read-only real-source AST metadata only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import mpw_cpanel_buyer_source_contract_readonly_c108 as audit


DATA = {
    "mpw_commerce/checkout_views.py": (
        "def checkout_challenge(): pass\n"
        "def checkout_verify_signature(): pass\n"
        "def checkout_invoice(): pass\n"
        "def checkout_status(): pass\n"),
    "mpw_commerce/product_checkout_page.py":
        "def product_checkout_page(): pass\n",
    "mpw_commerce/purchase_history.py":
        "def purchased_downloads(): pass\n",
    "mpw_commerce/customer_auth.py": (
        "class CustomerLogin: pass\n"
        "class CustomerLogout: pass\n"
        "def customer_register(): pass\n"),
    "mpw_commerce/buyer_orders.py": (
        "def _buyer_has_valid_email(): pass\n"
        "def _cart_scope_matches(): pass\n"
        "def create_digital_order(): pass\n"),
    "mpw_commerce/policy.py": (
        "class CommercePolicyError(Exception): pass\n"
        "def order_snapshot(): pass\n"),
    "mpw_commerce/entitlements.py": (
        "def can_access_purchased_digital_item():\n"
        "    return require_persisted_receipt_scope()\n"),
    "mpw_commerce/downloads.py": (
        "def download_paid_item():\n"
        "    return can_access_purchased_digital_item()\n"),
    "mpw_commerce/urls.py": (
        "urlpatterns = ['commerce/checkout/order/',"
        "'commerce/download/<int:item_id>/']\n"),
    "gateway_contract/merchant_binding.py":
        "def resolve_registered_merchant(): pass\n",
    "mpw_native_checkout/wallet_ownership.py":
        "def proven_merchant_wallets(): pass\n",
    "services/mpw_trx_commercial_web.py": "def commercial_page(): pass\n",
    "services/mpw_trx_public_pages.py": "def public_page(): pass\n",
}


class ReadOnlyCpanelAstAuditTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="mpw-c108-")
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name) / "fixture_checkout_root"
        self.root.mkdir()
        for path, value in DATA.items():
            dest = self.root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(value, encoding="utf-8")

    def run_audit(self):
        return audit.inspect(self.root)

    def test_all_thirteen_synthetic_sources_produce_valid_allowlist(self):
        report = self.run_audit()
        self.assertTrue(report["root_valid"])
        self.assertEqual(set(report["module_states"]), set(audit.FILES))
        self.assertEqual(len(report["module_states"]), 13)
        self.assertTrue(all(s["present"] and s["parseable"]
                            and s["exports_present"]
                            for s in report["module_states"].values()))

    def test_all_eleven_synthetic_ast_signals_true(self):
        self.assertTrue(all(self.run_audit()["source_signals"].values()))

    def test_no_customer_data_or_execution_claims(self):
        r = self.run_audit()
        for field in ("application_imported", "customer_data_read",
                      "database_read", "network_used", "files_modified",
                      "release_permitted", "payment_proven",
                      "runtime_passenger_proven"):
            with self.subTest(field=field):
                self.assertIs(r[field], False)

    def test_never_prints_source_bytes_or_hashes(self):
        r = json.dumps(self.run_audit())
        self.assertNotIn("def checkout_challenge", r)
        self.assertNotIn("sha256", r)
        self.assertNotIn(str(self.root), r)

    def test_missing_buyer_handler_reported_without_python_import(self):
        (self.root / "mpw_commerce/buyer_orders.py").unlink()
        r = self.run_audit()
        self.assertFalse(r["source_signals"]["source_buyer_order_handler_defined"])
        self.assertFalse(r["module_states"]["mpw_commerce/buyer_orders.py"]["present"])

    def test_missing_one_original_customer_source_not_reported_present(self):
        (self.root / "mpw_commerce/customer_auth.py").unlink()
        r = self.run_audit()
        self.assertFalse(r["module_states"]["mpw_commerce/customer_auth.py"]["present"])
        self.assertFalse(r["source_signals"]["source_customer_auth_exports_defined"])

    def test_corrupt_python_reports_parse_failure(self):
        p = self.root / "mpw_commerce/checkout_views.py"
        p.write_text("def checkout_challenge(:\n")
        r = self.run_audit()
        self.assertTrue(r["module_states"]["mpw_commerce/checkout_views.py"]["present"])
        self.assertFalse(r["module_states"]["mpw_commerce/checkout_views.py"]["parseable"])
        self.assertFalse(r["source_signals"]["source_checkout_handlers_defined"])

    def test_non_utf8_file_reports_parse_failure(self):
        (self.root / "mpw_commerce/checkout_views.py").write_bytes(b"\xff\xfe")
        r = self.run_audit()
        self.assertTrue(r["module_states"]["mpw_commerce/checkout_views.py"]["present"])
        self.assertFalse(r["module_states"]["mpw_commerce/checkout_views.py"]["parseable"])

    def test_final_symlink_to_external_code_denied(self):
        p = self.root / "mpw_commerce/checkout_views.py"
        p.unlink()
        outside = Path(self.work.name) / "outside.py"
        outside.write_text(DATA["mpw_commerce/checkout_views.py"])
        p.symlink_to(outside)
        r = self.run_audit()
        self.assertFalse(r["module_states"]["mpw_commerce/checkout_views.py"]["present"])

    def test_intermediate_symlink_to_external_package_denied(self):
        source = self.root / "gateway_contract"
        source.rename(self.root / "old_contract")
        ext = Path(self.work.name) / "external_contract"
        ext.mkdir()
        (ext / "merchant_binding.py").write_text(DATA["gateway_contract/merchant_binding.py"])
        source.symlink_to(ext, target_is_directory=True)
        r = self.run_audit()
        self.assertFalse(r["module_states"]["gateway_contract/merchant_binding.py"]["present"])

    def test_root_symlink_denied(self):
        alias = Path(self.work.name) / "fake"
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertFalse(audit.inspect(alias)["root_valid"])

    def test_unrelated_absolute_root_denied(self):
        self.assertFalse(audit.inspect(Path(self.work.name))["root_valid"])

    def test_oversize_file_not_read(self):
        p = self.root / "mpw_commerce/customer_auth.py"
        p.write_bytes(b"a" * (audit.LIMIT + 1))
        r = self.run_audit()
        self.assertFalse(r["module_states"]["mpw_commerce/customer_auth.py"]["present"])

    def test_directory_disguised_as_py_denied(self):
        p = self.root / "mpw_commerce/customer_auth.py"
        p.unlink()
        p.mkdir()
        self.assertFalse(self.run_audit()["module_states"][
            "mpw_commerce/customer_auth.py"]["present"])

    def test_missing_receipt_scope_call_is_not_certified(self):
        p = self.root / "mpw_commerce/entitlements.py"
        p.write_text("def can_access_purchased_digital_item(): return True\n")
        self.assertFalse(self.run_audit()["source_signals"][
            "source_paid_entitlement_invokes_receipt_scope"])

    def test_missing_download_entitlement_call_not_certified(self):
        p = self.root / "mpw_commerce/downloads.py"
        p.write_text("def download_paid_item(): return 'unprotected'\n")
        self.assertFalse(self.run_audit()["source_signals"][
            "source_paid_download_invokes_entitlement"])

    def test_missing_merchant_binding_not_certified(self):
        p = self.root / "gateway_contract/merchant_binding.py"
        p.write_text("def wrong_function(): pass\n")
        self.assertFalse(self.run_audit()["source_signals"][
            "source_merchant_binding_resolver_defined"])

    def test_missing_direct_route_literal_not_certified(self):
        p = self.root / "mpw_commerce/urls.py"
        p.write_text("urlpatterns = []\n")
        self.assertFalse(self.run_audit()["source_signals"][
            "source_checkout_order_route_literal"])

    def test_source_signals_are_only_bools_from_fixed_names(self):
        r = self.run_audit()
        self.assertEqual(set(r["source_signals"]), set(audit._SIGNAL_NAMES))
        self.assertTrue(all(type(v) is bool for v in r["source_signals"].values()))

    def test_readonly_ast_scanner_never_mutates_source_files(self):
        before = {path: (self.root / path).read_bytes() for path in DATA}
        self.run_audit()
        after = {path: (self.root / path).read_bytes() for path in DATA}
        self.assertEqual(before, after)

    def test_cli_with_nonowner_fixture_environment_never_claims_release(self):
        proc = subprocess.run(
            [sys.executable, "-B", "-m",
             "scripts.mpw_cpanel_buyer_source_contract_readonly_c108"],
            capture_output=True, timeout=8,
            cwd=Path(__file__).resolve().parents[1],
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode(errors="replace"))
        self.assertTrue(proc.stdout.decode().startswith(audit.PREFIX))
        data = json.loads(proc.stdout.decode()[len(audit.PREFIX):])
        self.assertFalse(data["release_permitted"])
        self.assertFalse(data["customer_data_read"])
        self.assertFalse(data["payment_proven"])


if __name__ == "__main__":
    unittest.main()
