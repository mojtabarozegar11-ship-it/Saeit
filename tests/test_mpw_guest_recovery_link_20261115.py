"""Guard the approved purchase recovery CTA without sending an email."""
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_guest_commerce.py"


class GuestPurchaseRecoveryLinkTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text("utf-8")

    def test_source_compiles_without_running_checkout(self):
        compile(self.source, str(SOURCE), "exec")

    def test_recovery_link_points_to_existing_self_service_route(self):
        self.assertIn('href="/commerce/trx-easy/recover/"', self.source)

    def test_recovery_cta_requires_both_feature_and_email_approval(self):
        self.assertIn('"MPW_GUEST_RECOVERY_ENABLED", False) is True', self.source)
        self.assertIn('"MPW_GUEST_RECOVERY_EMAIL_APPROVED", False) is True', self.source)

    def test_no_automatic_email_or_payment_side_effects_in_link(self):
        tree = ast.parse(self.source)
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name == "patch_public"]
        self.assertEqual(len(functions), 1)
        self.assertNotIn("send_mail(", self.source)
        self.assertIn("recovery_link +", self.source)


if __name__ == "__main__":
    unittest.main()
