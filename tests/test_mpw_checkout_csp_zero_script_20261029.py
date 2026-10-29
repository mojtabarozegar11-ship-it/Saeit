"""S-01 non-transactional checkout CSP regression tests."""
import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mpw_checkout_csp_zero_script_guard_20261029.py"
spec = importlib.util.spec_from_file_location("mpw_csp_zero_script_guard", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CheckoutZeroScriptCSPTests(unittest.TestCase):
    def test_no_inline_script_and_one_inline_script_both_fail_closed(self):
        # Exercises the same exact-string patch contract as the cPanel preview,
        # without database, filesystem mutation, orders, payments or credentials.
        module.selftest()

    def test_unknown_checkout_source_is_not_patched(self):
        with self.assertRaisesRegex(RuntimeError, "Expected strict CSP implementation"):
            module.build(b"def unrelated_checkout(): pass\n")

    def test_source_drift_rejected_before_any_release_write(self):
        with self.assertRaisesRegex(RuntimeError, "source SHA drift"):
            module.release_preconditions(b"not-the-pinned-checkout-source")

    def test_release_uses_private_directory_advisory_lock(self):
        self.assertTrue(callable(module.release_lock))
        self.assertGreaterEqual(module.MIN_RELEASE_HEADROOM, 20 * 1024 * 1024)

    def test_publish_requires_explicit_release_gate_before_any_file_access(self):
        with patch.dict(os.environ, {"MPW_CSP_RELEASE_APPROVED": ""}):
            with self.assertRaisesRegex(RuntimeError, "blocked without explicit release gate"):
                module.publish("40808335828")


    def test_publish_requires_independent_offhost_restore_before_guard(self):
        with patch.dict(os.environ, {
            "MPW_CSP_RELEASE_APPROVED": "YES",
            "MPW_CSP_OFFHOST_RESTORE_VERIFIED": "",
            "MPW_CSP_PASSENGER_DB_AUTHORITY_VERIFIED": "YES",
        }):
            with patch.object(module, "guard", side_effect=AssertionError("guard must not run")):
                with self.assertRaisesRegex(RuntimeError, "off-host restore not verified"):
                    module.publish("40808335828")

    def test_publish_requires_passenger_db_authority_before_guard(self):
        with patch.dict(os.environ, {
            "MPW_CSP_RELEASE_APPROVED": "YES",
            "MPW_CSP_OFFHOST_RESTORE_VERIFIED": "YES",
            "MPW_CSP_PASSENGER_DB_AUTHORITY_VERIFIED": "",
        }):
            with patch.object(module, "guard", side_effect=AssertionError("guard must not run")):
                with self.assertRaisesRegex(RuntimeError, "Passenger database authority not verified"):
                    module.publish("40808335828")

    def test_synthetic_checkout_sql_guard_allows_only_select(self):
        executed = []
        def execute(sql, params, many, context):
            executed.append(sql)
            return "read-ok"
        self.assertEqual(
            module._read_only_checkout_sql(execute, " SELECT 1", (), False, {}),
            "read-ok",
        )
        self.assertEqual(executed, [" SELECT 1"])
        for statement in (
            "INSERT INTO orders VALUES (1)", "UPDATE orders SET paid=1",
            "DELETE FROM orders", "WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x",
            "BEGIN", "PRAGMA writable_schema=ON", "/* hidden */ SELECT 1",
        ):
            with self.subTest(statement=statement):
                with self.assertRaisesRegex(RuntimeError, "non-SELECT"):
                    module._read_only_checkout_sql(execute, statement, (), False, {})
        self.assertEqual(executed, [" SELECT 1"])

    def test_rollback_requires_authorization_before_any_file_access(self):
        with patch.dict(os.environ, {"MPW_CSP_RELEASE_APPROVED": ""}):
            with patch.object(module, "guard", side_effect=AssertionError("guard must not run")):
                with self.assertRaisesRegex(RuntimeError, "rollback blocked without explicit release gate"):
                    module.rollback("40808335828")

    def test_rollback_serializes_with_publish_lock(self):
        with patch.dict(os.environ, {"MPW_CSP_RELEASE_APPROVED": "YES"}):
            from contextlib import contextmanager
            calls = []
            @contextmanager
            def lock():
                calls.append("lock-enter")
                yield
                calls.append("lock-exit")
            with patch.object(module, "guard", side_effect=lambda: calls.append("guard")), \
                 patch.object(module, "release_lock", side_effect=lock), \
                 patch.object(module, "_rollback_locked", side_effect=lambda run: calls.append("rollback")):
                module.rollback("40808335828")
            self.assertEqual(calls, ["guard", "lock-enter", "rollback", "lock-exit"])


if __name__ == "__main__":
    unittest.main()
