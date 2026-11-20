"""Static contract tests for the private MOJ PROP identity adapter."""
from pathlib import Path
import unittest


class SimulationIdentityAdapterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.source = (cls.root / "simulation_identity_adapter.py").read_text(
            encoding="utf-8"
        )

    def test_adapter_is_database_scoped_and_fail_closed(self):
        source = self.source
        for marker in (
            "MOJPROP_DB_ALIAS",
            "transaction.atomic(using=MOJPROP_DB_ALIAS)",
            ".objects.using(MOJPROP_DB_ALIAS)",
            ".select_for_update()",
            "hmac.compare_digest",
            "consumed_at",
            "attempt_count",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("auth_user", source)
        self.assertNotIn("send_mail", source)

    def test_adapter_never_enables_commerce_or_live_execution(self):
        source = self.source
        for forbidden in (
            "MPW_MOJPROP_PLAN1_ROUTE_ENABLED = True",
            "MPW_MOJPROP_PLAN1_LIVE_INVOICE_ENABLED = True",
            "create_invoice",
            "broadcast",
            "payout",
            "place_order",
        ):
            self.assertNotIn(forbidden, source)

    def test_adapter_uses_digest_only_for_email_and_challenge_code(self):
        source = self.source
        for marker in (
            "email_digest",
            "subject_key",
            "code_digest",
            "secrets.token_hex",
            "return int(challenge.identity_id)",
        ):
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
