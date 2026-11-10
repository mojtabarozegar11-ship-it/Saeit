"""Offline contract tests for the read-only MojPlayWin host evidence command.

Never invoke the command, a database, the production site, or an order writer.
"""
import ast
import unittest
from pathlib import Path


PROBE = Path(__file__).resolve().parents[1] / "scripts/mpw_guest_runtime_readonly_readiness.py"
SOURCE = PROBE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def literal_assignment(name):
    node = next(
        stmt for stmt in TREE.body
        if isinstance(stmt, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == name for t in stmt.targets)
    )
    return ast.literal_eval(node.value)


class RuntimeEvidenceReadOnlyContract(unittest.TestCase):
    def test_required_migrations_are_exact(self):
        pairs = {(a, n) for a, n, _ in literal_assignment("MIGRATIONS")}
        self.assertEqual(pairs, {
            ("core", "0049_mpw_guest_email_recovery"),
            ("mpw_commerce", "0004_guesttrxdelivery"),
        })
        self.assertNotIn(("core", "0040_agenttask_bridge_idempotency"), pairs)

    def test_required_tables_are_explicit(self):
        mapping = {(a, n): set(t) for a, n, t in literal_assignment("MIGRATIONS")}
        self.assertEqual(mapping[("core", "0049_mpw_guest_email_recovery")], {
            "core_guestorderemail", "core_guestrecoverytoken",
            "core_guestrecoveryrate"})
        self.assertEqual(mapping[("mpw_commerce", "0004_guesttrxdelivery")], {
            "mpw_commerce_guesttrxdelivery"})

    def test_recovery_send_and_invoice_send_remain_separate_flags(self):
        self.assertEqual(set(literal_assignment("FEATURE_FLAGS")), {
            "MPW_GUEST_EMAIL_SEND_APPROVED",
            "MPW_GUEST_RECOVERY_EMAIL_APPROVED",
        })

    def test_no_order_or_customer_model_is_imported(self):
        imports = [
            a.name for node in ast.walk(TREE)
            if isinstance(node, ast.ImportFrom)
            for a in node.names
        ]
        self.assertNotIn("Order", imports)
        self.assertNotIn("PaymentIntent", imports)
        self.assertNotIn("GuestOrderEmail", imports)

    def test_only_one_literal_read_only_sql_query(self):
        calls = [
            node for node in ast.walk(TREE)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
        ]
        self.assertEqual(len(calls), 1)
        strings = [
            node.value for node in ast.walk(calls[0])
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        self.assertTrue(any(s.lstrip().upper().startswith("SELECT") for s in strings))
        forbidden = ("INSERT", "UPDATE", "DELETE", "ALTER", "DROP", "CREATE")
        self.assertFalse(any(word in s.upper().split()[:1]
                             for s in strings for word in forbidden))

    def test_production_user_and_bootstrap_guards_are_present(self):
        self.assertIn("WRONG_CPANEL_USER", SOURCE)
        self.assertIn("PUBLIC_BOOTSTRAP_MISMATCH", SOURCE)
        self.assertIn("PRODUCTION_ENV_NOT_EXPLICIT", SOURCE)
        self.assertIn("UNEXPECTED_DJANGO_SETTINGS", SOURCE)
        self.assertIn("APP='/home/zomorod2/Saeit-staging'", SOURCE)

    def test_no_mail_order_or_migration_command_invocation(self):
        forbidden_calls = {
            "send_mail", "send", "issue", "reserve_commercial_intent",
            "migrate", "call_command", "subprocess", "Popen", "system",
            "exec", "eval", "unlink", "write_text", "write_bytes",
        }
        invoked = {
            node.func.attr if isinstance(node.func, ast.Attribute)
            else node.func.id
            for node in ast.walk(TREE) if isinstance(node, ast.Call)
            if isinstance(node.func, (ast.Attribute, ast.Name))
        }
        self.assertFalse(invoked & forbidden_calls)

    def test_output_never_certifies_commercial_release(self):
        self.assertIn('"commercial_release_certified": False', SOURCE)
        self.assertIn('"customer_rows_read": 0', SOURCE)
        self.assertIn('"payments_created": 0', SOURCE)
        self.assertIn('"emails_sent": 0', SOURCE)
        self.assertIn('stop("RUNTIME_METADATA_UNAVAILABLE")', SOURCE)


if __name__ == "__main__":
    unittest.main()
