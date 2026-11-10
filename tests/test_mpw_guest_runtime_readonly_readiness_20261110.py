"""Offline contract tests for the read-only MojPlayWin host evidence command.

Never invoke the command, a database, the production site, or an order writer.
"""
import ast
import runpy
import tempfile
import unittest
from pathlib import Path


PROBE = Path(__file__).resolve().parents[1] / "scripts/mpw_guest_runtime_readonly_readiness.py"
SOURCE = PROBE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
HELPERS = runpy.run_path(str(PROBE), run_name="mpw_offline_only")
ROOT_MATCH = HELPERS["registered_passenger_root"]
SOURCE_SHAPE = HELPERS["checkout_source_shape"]


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

    def test_critical_runtime_module_fingerprints_are_explicit(self):
        self.assertEqual(set(literal_assignment("SOURCE_PATHS")), {
            "services/mpw_trx_guest_commerce.py",
            "services/mpw_trx_email_recovery.py",
            "services/mpw_trx_commercial_web.py",
            "services/mpw_trx_commercial_context.py",
            "services/mpw_trx_public_catalog.py",
            "services/mpw_trx_guest_delivery.py",
            "services/mpw_trx_public_pages.py",
            "config/urls.py",
        })
        self.assertIn('"source_inventory_complete": all(', SOURCE)
        self.assertNotIn(".env", literal_assignment("SOURCE_PATHS"))

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

    def test_single_declared_absolute_passenger_root_is_accepted(self):
        self.assertTrue(ROOT_MATCH("PassengerAppRoot /home/zomorod2/mojplaywin.com\n"))
        self.assertTrue(ROOT_MATCH(
            'PassengerAppRoot "/home/zomorod2/mojplaywin.com/" # cPanel\n'
        ))

    def test_single_declared_relative_passenger_root_is_accepted(self):
        self.assertTrue(ROOT_MATCH("PassengerAppRoot mojplaywin.com\n"))
        self.assertTrue(ROOT_MATCH("passengerapproot 'mojplaywin.com'\n"))

    def test_comments_and_absent_passenger_root_fail_closed(self):
        self.assertFalse(ROOT_MATCH("# PassengerAppRoot /home/zomorod2/mojplaywin.com\n"))
        self.assertFalse(ROOT_MATCH("PassengerAppEnv production\n"))

    def test_duplicate_and_wrong_passenger_root_fail_closed(self):
        self.assertFalse(ROOT_MATCH(
            "PassengerAppRoot /home/zomorod2/mojplaywin.com\n"
            "PassengerAppRoot /home/zomorod2/other-site\n"
        ))
        self.assertFalse(ROOT_MATCH("PassengerAppRoot /home/zomorod2/other-site\n"))

    def test_malformed_quoted_passenger_root_fails_closed(self):
        self.assertFalse(ROOT_MATCH("PassengerAppRoot '/home/zomorod2/mojplaywin.com\n"))
        self.assertFalse(ROOT_MATCH('PassengerAppRoot /home/zomorod2/mojplaywin.com"\n'))

    def test_production_user_and_bootstrap_guards_are_present(self):
        self.assertIn("WRONG_CPANEL_USER", SOURCE)
        self.assertIn("PUBLIC_BOOTSTRAP_MISMATCH", SOURCE)
        self.assertIn("PRODUCTION_ENV_NOT_EXPLICIT", SOURCE)
        self.assertIn("UNEXPECTED_DJANGO_SETTINGS", SOURCE)
        self.assertIn("PUBLIC_PASSENGER_ROOT_UNSAFE", SOURCE)
        self.assertIn("PUBLIC_PASSENGER_ROOT_MISMATCH", SOURCE)
        self.assertIn('"passenger_registered_root_matches_public": True', SOURCE)
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

    def test_missing_checkout_modules_have_no_source_shape_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = SOURCE_SHAPE(Path(directory))
        self.assertEqual(
            evidence["meaning"], "source_shape_only_not_runtime_or_payment_proof")
        self.assertFalse(any(value for key, value in evidence.items()
                             if key != "meaning"))

    def test_static_contract_detects_bound_order_claim_and_atomic_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            services = Path(directory) / "services"
            services.mkdir()
            (services / "mpw_trx_guest_commerce.py").write_text(
                "def _dispatch(request):\n"
                "    return bound_checkout(request)\n", encoding="utf-8")
            (services / "mpw_trx_email_recovery.py").write_text(
                "def _posted_email(request):\n"
                "    return request\n"
                "def bound_checkout(request):\n"
                "    with transaction.atomic():\n"
                "        GuestOrderEmail.objects.create()\n", encoding="utf-8")
            evidence = SOURCE_SHAPE(Path(directory))
        self.assertTrue(all(value for key, value in evidence.items()
                            if key != "meaning"))

    def test_syntactically_invalid_recovery_never_passes_source_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            services = Path(directory) / "services"
            services.mkdir()
            (services / "mpw_trx_guest_commerce.py").write_text(
                "def _dispatch(request):\n"
                "    return bound_checkout(request)\n", encoding="utf-8")
            (services / "mpw_trx_email_recovery.py").write_text(
                "def bound_checkout(:\n", encoding="utf-8")
            evidence = SOURCE_SHAPE(Path(directory))
        self.assertTrue(evidence["adapter_dispatch_calls_bound_checkout"])
        self.assertFalse(evidence["recovery_syntax_valid"])
        self.assertFalse(evidence["recovery_defines_bound_checkout"])

    def test_plain_binding_name_without_atomic_claim_is_insufficient(self):
        with tempfile.TemporaryDirectory() as directory:
            services = Path(directory) / "services"
            services.mkdir()
            (services / "mpw_trx_guest_commerce.py").write_text(
                "def _dispatch(request):\n"
                "    return bound_checkout(request)\n", encoding="utf-8")
            (services / "mpw_trx_email_recovery.py").write_text(
                "def _posted_email(request): return request\n"
                "def bound_checkout(request): return request\n", encoding="utf-8")
            evidence = SOURCE_SHAPE(Path(directory))
        self.assertTrue(evidence["recovery_defines_bound_checkout"])
        self.assertFalse(evidence[
            "recovery_bound_checkout_references_guest_order_claim"])
        self.assertFalse(evidence[
            "recovery_bound_checkout_references_atomic_scope"])

    def test_missing_route_is_isolated_from_migration_evidence(self):
        route_guard = [
            node for node in ast.walk(TREE) if isinstance(node, ast.ExceptHandler)
            and isinstance(node.type, ast.Name) and node.type.id == "Resolver404"
        ]
        self.assertEqual(len(route_guard), 1)
        self.assertIn('"resolved": False', SOURCE)
        self.assertIn('"migration_evidence": migration_evidence', SOURCE)
        self.assertIn('"checkout_code_source_shape_only": checkout_source_shape(APP)', SOURCE)

    def test_output_never_certifies_commercial_release(self):
        self.assertIn('"commercial_release_certified": False', SOURCE)
        self.assertIn('"customer_rows_read": 0', SOURCE)
        self.assertIn('"payments_created": 0', SOURCE)
        self.assertIn('"emails_sent": 0', SOURCE)
        self.assertIn('stop("RUNTIME_METADATA_UNAVAILABLE")', SOURCE)


if __name__ == "__main__":
    unittest.main()
