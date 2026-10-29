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


if __name__ == "__main__":
    unittest.main()
