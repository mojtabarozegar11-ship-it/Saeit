"""Offline regression coverage for cPanel read-only checkout source traversal."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from scripts.mpw_checkout_import_closure_readonly_20261115 import (
    MAX_MODULES, START_MODULES, approved_module, static_imports,
    readable_module, import_closure,
)


class CheckoutImportClosureTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def module(self, name, source):
        p = self.root.joinpath(*name.split(".")).with_suffix(".py")
        p.parent.mkdir(exist_ok=True, parents=True)
        p.write_text(source, encoding="utf8")

    def test_approved_module_scope_is_bounded(self):
        self.assertTrue(approved_module("services.mpw_trx_asset_integrity"))
        self.assertFalse(approved_module("services.stripe_private"))
        self.assertFalse(approved_module("os"))
        self.assertFalse(approved_module("../../config.env"))

    def test_absolute_imports_discovered_without_importing(self):
        names = static_imports(
            "from services.mpw_trx_asset_integrity import private_asset_matches_sha256\n"
            "import services.mpw_trx_guest_delivery\nimport smtplib\n"
        )
        self.assertIn("services.mpw_trx_asset_integrity", names)
        self.assertIn("services.mpw_trx_guest_delivery", names)
        self.assertNotIn("smtplib", names)

    def test_missing_entrypoints_detected(self):
        result = import_closure(self.root)
        self.assertEqual(result["missing_count"], len(START_MODULES))
        self.assertFalse(result["checkout_deployable_verified"])
        self.assertEqual(result["orders_created"], 0)

    def test_missing_transitive_checkout_helper_detected(self):
        for name in START_MODULES:
            self.module(name, "x = 1\n")
        self.module("services.mpw_trx_commercial_web",
                    "from services.mpw_trx_asset_integrity import verified_private_stream_sha256\n")
        result = import_closure(self.root)
        self.assertIn("services.mpw_trx_asset_integrity", result["missing_import_modules"])
        self.assertEqual(result["missing_count"], 1)

    def test_existing_transitive_helper_clears_missing(self):
        for name in START_MODULES:
            self.module(name, "x = 1\n")
        self.module("services.mpw_trx_commercial_web",
                    "from services.mpw_trx_asset_integrity import private_asset_matches_sha256\n")
        self.module("services.mpw_trx_asset_integrity", "x = 1\n")
        result = import_closure(self.root)
        self.assertEqual(result["missing_count"], 0)
        self.assertTrue(result["checkout_deployable_verified"])

    def test_syntax_error_marks_not_deployable(self):
        for name in START_MODULES:
            self.module(name, "x = 1\n")
        self.module("services.mpw_trx_public_catalog", "def broken(:\n")
        result = import_closure(self.root)
        self.assertEqual(result["syntax_error_count"], 1)
        self.assertFalse(result["checkout_deployable_verified"])

    def test_symlink_checkout_helper_is_rejected(self):
        for name in START_MODULES:
            self.module(name, "x = 1\n")
        self.module("services.mpw_trx_guest_delivery", "import services.mpw_trx_asset_integrity")
        target = self.root / "real_content.py"
        target.write_text("x=1")
        link = self.root / "services/mpw_trx_asset_integrity.py"
        link.symlink_to(target)
        result = import_closure(self.root)
        self.assertIn("services.mpw_trx_asset_integrity", result["missing_import_modules"])

    def test_oversized_module_cannot_consume_unbounded_memory(self):
        self.module("services.mpw_trx_public_catalog", "x=1\n" * 150000)
        self.assertIsNone(readable_module(self.root, "services.mpw_trx_public_catalog"))

    def test_unapproved_module_cannot_read_secret(self):
        self.module("config.urls", "x=1\n")
        self.assertIsNone(readable_module(self.root, "config.env"))

    def test_missing_directory_does_not_throw(self):
        self.assertIsNone(readable_module(self.root, "services.mpw_trx_asset_integrity"))

    def test_exact_start_module_count(self):
        self.assertEqual(len(START_MODULES), 5)

    def test_traversal_limit_is_explicit(self):
        self.assertLessEqual(MAX_MODULES, 200)

    def test_report_does_not_claim_payment_or_deploy(self):
        result = import_closure(self.root)
        self.assertIs(result["live_payment_enabled"], False)
        self.assertIs(result["customer_data_read"], False)
        self.assertEqual(result["module_paths_written"], 0)

    def test_noncheckout_imports_not_traversed(self):
        for name in START_MODULES:
            self.module(name, "import logging\nfrom pathlib import Path\n")
        result = import_closure(self.root)
        self.assertEqual(result["inspected_modules"], 5)
