"""Non-mutating source contracts for recovered, owner-required buyer email.

These are OFFLINE checks of the reviewed source's invariants; they do not
send SMTP, create buyer orders, run DB migrations or verify TRX payment.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / "services/mpw_trx_email_recovery.py"
MODELS = ROOT / "core/guest_recovery_models.py"
MIGRATION = ROOT / "core/migrations/0049_mpw_guest_email_recovery.py"
CORE = ROOT / "core/models.py"
SETTINGS = ROOT / "config/settings.py"
COVERAGE = ROOT / "scripts/mpw_checkout_source_coverage_20261114.py"


class RecoveredBuyerEmailSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = RECOVERY.read_text(encoding="utf-8")
        cls.models = MODELS.read_text(encoding="utf-8")
        cls.migration = MIGRATION.read_text(encoding="utf-8")
        cls.core = CORE.read_text(encoding="utf-8")
        cls.settings = SETTINGS.read_text(encoding="utf-8")
        cls.svc_ast = ast.parse(cls.service)
        cls.model_ast = ast.parse(cls.models)
        cls.migration_ast = ast.parse(cls.migration)

    def test_01_durable_buyer_email_service_restored(self):
        self.assertTrue(RECOVERY.is_file())

    def test_02_guest_email_model_source_restored(self):
        self.assertTrue(MODELS.is_file())

    def test_03_migration_0049_restored(self):
        self.assertTrue(MIGRATION.is_file())

    def test_04_all_recovered_python_sources_parse(self):
        self.assertIsInstance(self.svc_ast, ast.Module)
        self.assertIsInstance(self.model_ast, ast.Module)
        self.assertIsInstance(self.migration_ast, ast.Module)

    def test_05_core_models_register_all_three_claim_classes(self):
        self.assertIn("from .guest_recovery_models import GuestOrderEmail, GuestRecoveryToken, GuestRecoveryRate", self.core)

    def test_06_core_models_registration_is_unique(self):
        self.assertEqual(self.core.count("from .guest_recovery_models import"), 1)

    def test_07_three_model_classes_exist(self):
        names = {x.name for x in self.model_ast.body if isinstance(x, ast.ClassDef)}
        self.assertEqual(names, {"GuestOrderEmail", "GuestRecoveryToken", "GuestRecoveryRate"})

    def test_08_guest_email_claim_is_one_to_one_order(self):
        self.assertIn("models.OneToOneField(", self.models)
        self.assertIn('"core.Order"', self.models)

    def test_09_email_claim_preserves_order_not_cascade(self):
        self.assertIn("on_delete=models.PROTECT", self.models)

    def test_10_guest_email_reassignment_rejected(self):
        self.assertIn('raise ValidationError("Checkout email cannot be reassigned")', self.models)

    def test_11_email_address_is_validated_django_field(self):
        self.assertIn("models.EmailField(max_length=254)", self.models)

    def test_12_email_digest_has_index(self):
        self.assertIn("models.CharField(max_length=64, db_index=True)", self.models)

    def test_13_recovery_token_digest_is_unique(self):
        self.assertIn("token_digest = models.CharField(max_length=64, unique=True)", self.models)

    def test_14_recovery_token_has_expiry(self):
        self.assertIn("expires_at = models.DateTimeField()", self.models)

    def test_15_recovery_token_has_single_use_marker(self):
        self.assertIn("consumed_at = models.DateTimeField(null=True, blank=True)", self.models)

    def test_16_recovery_rate_bucket_is_unique(self):
        self.assertIn("bucket = models.CharField(max_length=64, unique=True)", self.models)

    def test_17_models_do_not_store_plaintext_recovery_secret(self):
        self.assertNotIn("plaintext_token = models.", self.models)
        self.assertNotIn("recovery_code = models.", self.models)

    def test_18_model_permissions_disabled_by_default(self):
        self.assertEqual(self.models.count("default_permissions = ()"), 3)

    def test_19_migration_parent_is_actual_0040(self):
        self.assertIn('("core", "0040_commercefunnelevent")', self.migration)
        self.assertTrue((ROOT/"core/migrations/0040_commercefunnelevent.py").exists())

    def test_20_schema_has_exactly_three_create_models(self):
        self.assertEqual(self.migration.count("migrations.CreateModel("), 3)

    def test_21_migration_creates_order_email(self):
        self.assertIn('name="GuestOrderEmail"', self.migration)

    def test_22_migration_creates_recovery_token(self):
        self.assertIn('name="GuestRecoveryToken"', self.migration)

    def test_23_migration_creates_rate_limit(self):
        self.assertIn('name="GuestRecoveryRate"', self.migration)

    def test_24_migration_preserves_order_protect(self):
        self.assertIn("django.db.models.deletion.PROTECT", self.migration)

    def test_25_migration_has_no_runtime_data_migration(self):
        self.assertNotIn("migrations.RunPython(", self.migration)
        self.assertNotIn("migrations.RunSQL(", self.migration)

    def test_26_recovery_service_requires_both_independent_approvals(self):
        self.assertIn('getattr(settings, "MPW_GUEST_RECOVERY_ENABLED", False) is True', self.service)
        self.assertIn('getattr(settings, "MPW_GUEST_RECOVERY_EMAIL_APPROVED", False) is True', self.service)

    def test_27_main_settings_do_not_enable_recovery(self):
        self.assertNotIn("MPW_GUEST_RECOVERY_ENABLED = True", self.settings)
        self.assertNotIn("MPW_GUEST_RECOVERY_EMAIL_APPROVED = True", self.settings)

    def test_28_guest_checkout_requires_post_body_email(self):
        self.assertIn('getattr(request, "method", None) != "POST"', self.service)
        self.assertIn('raise ValueError("Buyer email requires a checkout POST")', self.service)

    def test_29_duplicate_email_values_never_silently_selected(self):
        self.assertIn('raise ValueError("Ambiguous checkout email fields")', self.service)
        self.assertIn('raise ValueError("Multiple buyer email fields")', self.service)

    def test_30_missing_email_never_silently_accepted(self):
        self.assertIn('raise ValueError("Exactly one buyer email is required")', self.service)

    def test_31_durable_order_claim_imported_by_service(self):
        self.assertIn("GuestOrderEmail, GuestRecoveryRate, GuestRecoveryToken", self.service)

    def test_32_no_walletless_payment_approval_from_email_alone(self):
        self.assertIn("verified_walletless_credit", self.service)

    def test_33_guest_recovery_uses_digest_not_plaintext_token_store(self):
        self.assertIn("token_digest", self.service)
        self.assertIn("secrets.token_urlsafe", self.service)

    def test_34_recovery_route_is_not_enabled_automatically(self):
        self.assertNotIn('from services.mpw_trx_email_recovery import', self.settings)

    def test_35_no_direct_smtp_in_initial_source_import(self):
        self.assertNotIn("EmailMessage(", self.service.split("def _recovery_enabled", 1)[0])

    def test_36_read_only_source_manifest_now_recognizes_recovered_parts(self):
        from scripts.mpw_checkout_source_coverage_20261114 import audit
        report = audit(ROOT)
        self.assertEqual(report["source_files_present"], 8)
        self.assertEqual(report["source_files_required"], 11)
        self.assertEqual(report["files"]["services/mpw_trx_email_recovery.py"], "present_regular_bounded")
        self.assertEqual(report["files"]["core/migrations/0049_mpw_guest_email_recovery.py"], "present_regular_bounded")

    def test_37_three_commerce_root_files_still_missing(self):
        from scripts.mpw_checkout_source_coverage_20261114 import audit
        report = audit(ROOT)
        for path in (
            "mpw_commerce/buyer_orders.py",
            "mpw_commerce/product_checkout_page.py",
            "mpw_commerce/templates/mpw_commerce/product_checkout.html",
        ):
            self.assertEqual(report["files"][path], "missing_or_unsafe")

    def test_38_source_restore_does_not_claim_store_live(self):
        from scripts.mpw_checkout_source_coverage_20261114 import audit
        report = audit(ROOT)
        self.assertFalse(report["live_dynamic_store_verified"])

    def test_39_source_restore_does_not_claim_payment(self):
        from scripts.mpw_checkout_source_coverage_20261114 import audit
        report = audit(ROOT)
        self.assertFalse(report["actual_payment_verified"])

    def test_40_source_restore_cannot_permit_release(self):
        from scripts.mpw_checkout_source_coverage_20261114 import audit
        report = audit(ROOT)
        self.assertFalse(report["release_permitted"])

    def test_41_restoration_keeps_collected_revenue_unknown(self):
        from scripts.mpw_checkout_source_coverage_20261114 import audit
        report = audit(ROOT)
        self.assertIsNone(report["actual_collected_revenue"])

    def test_42_root_model_and_migration_have_matching_claim_model_names(self):
        for model in ("GuestOrderEmail", "GuestRecoveryToken", "GuestRecoveryRate"):
            self.assertIn('name="' + model + '"', self.migration)
            self.assertIn("class " + model + "(", self.models)

    def test_43_source_does_not_auto_start_payment_or_worker(self):
        self.assertNotIn("MPW_TRX_AUTO_CHARGE = True", self.settings)
        self.assertNotIn("MPW_GUEST_RECOVERY_EMAIL_APPROVED=True", self.settings)

    def test_44_email_recovery_cannot_reassign_existing_guest_email(self):
        self.assertIn("self.order_id", self.models)
        self.assertIn("self.email_digest", self.models)
        self.assertIn("self.email_address", self.models)


if __name__ == "__main__":
    unittest.main()
