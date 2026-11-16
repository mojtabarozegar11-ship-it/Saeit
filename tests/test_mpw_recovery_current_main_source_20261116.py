import ast
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MojPlayWinRecoveryCurrentMainSourceTest(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_defaults_are_fail_closed_and_service_requires_both_flags(self):
        settings = self.read("config/settings.py")
        service = self.read("services/mpw_trx_email_recovery.py")
        self.assertIn('MPW_GUEST_RECOVERY_ENABLED = env.bool("MPW_GUEST_RECOVERY_ENABLED", default=False)', settings)
        self.assertIn('MPW_GUEST_RECOVERY_EMAIL_APPROVED = env.bool("MPW_GUEST_RECOVERY_EMAIL_APPROVED", default=False)', settings)
        self.assertIn('getattr(settings, "MPW_GUEST_RECOVERY_ENABLED", False) is True', service)
        self.assertIn('getattr(settings, "MPW_GUEST_RECOVERY_EMAIL_APPROVED", False) is True', service)
        self.assertNotIn("MPW_GUEST_RECOVERY_ENABLED = True", settings)
        self.assertNotIn("MPW_GUEST_RECOVERY_EMAIL_APPROVED = True", settings)

    def test_migration_is_after_current_main_and_additive_only(self):
        migration = self.read("core/migrations/0047_mpw_guest_email_recovery.py")
        tree = ast.parse(migration)
        source = ast.get_source_segment(migration, tree)
        self.assertIn('"0046_signal_free_subscription"', source)
        self.assertEqual(migration.count("migrations.CreateModel("), 3)
        self.assertNotIn("RunPython", migration)
        self.assertNotIn("RunSQL", migration)

    def test_claim_model_is_immutable_and_cleanup_keeps_claims(self):
        models = self.read("core/guest_recovery_models.py")
        cleanup = self.read("core/management/commands/mpw_purge_recovery_ephemeral.py")
        self.assertIn("Checkout email cannot be reassigned", models)
        self.assertIn("ORDER_EMAIL_CLAIMS_REMOVED=0", cleanup)
        self.assertNotIn("GuestOrderEmail.objects.filter", cleanup)

    def test_plaintext_token_is_not_persisted(self):
        service = self.read("services/mpw_trx_email_recovery.py")
        self.assertIn("token_digest=hashlib.sha256(code.encode", service)
        self.assertNotIn("token=code", service)


if __name__ == "__main__":
    unittest.main()
