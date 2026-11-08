"""Offline regression tests for the privacy-safe paid entitlement audit.

The live audit initializes Django against a fixed cPanel runtime root at module
import. Extract only its pure classification helper, avoiding production access,
payments, file serving and mutation while testing the exact shipped function.
"""

import ast
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def _readiness_function():
    source = (Path(__file__).resolve().parent / "mpw_paid_provenance_readonly_20261105.py").read_text(
        encoding="utf-8"
    )
    module = ast.parse(source)
    function = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "walletless_download_readiness"
    )
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "readiness-helper", "exec"), namespace)
    return namespace["walletless_download_readiness"]


class WalletlessReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classify = staticmethod(_readiness_function())

    def check_status(self, backend_result, expected_state, expected_download):
        service_package = types.ModuleType("services")
        service_package.__path__ = []
        service = types.ModuleType("services.mpw_walletless_commercial_intent")
        if isinstance(backend_result, Exception):
            def fail(*_args):
                raise backend_result
            service.commercial_buyer_status = fail
        else:
            service.commercial_buyer_status = lambda *_args: backend_result
        with patch.dict(sys.modules, {
            "services": service_package,
            "services.mpw_walletless_commercial_intent": service,
        }):
            result = self.classify(12, 15, verified=True)
        self.assertEqual(result, {"state": expected_state, "can_download": expected_download})
        self.assertEqual(set(result), {"state", "can_download"})

    def test_credit_must_be_verified(self):
        self.assertEqual(self.classify(12, 15, verified=False), {
            "state": "not_verified", "can_download": None,
        })

    def test_missing_credit_evidence(self):
        self.assertEqual(self.classify(12, 15, verified=None)["state"], "not_verified")

    def test_zero_intent_is_rejected(self):
        self.assertEqual(self.classify(0, 15, verified=True)["state"], "unavailable")

    def test_bool_id_is_not_valid_integer(self):
        self.assertEqual(self.classify(True, 15, verified=True)["state"], "unavailable")

    def test_paid_with_entitlement_is_ready_without_file_or_buyer_data(self):
        self.check_status({
            "status": "paid", "can_download": True,
            "download_path": "/private/customer/123",
        }, "ready", True)

    def test_awaiting_is_not_ready(self):
        self.check_status({"status": "awaiting", "can_download": False}, "not_ready", False)

    def test_review_is_not_ready(self):
        self.check_status({"status": "review", "can_download": False}, "not_ready", False)

    def test_missing_release_gate_fails_closed(self):
        self.check_status(RuntimeError("backend unavailable"), "unavailable", None)

    def test_unexpected_backend_response_fails_closed(self):
        self.check_status("buyer@example.org", "unavailable", None)


if __name__ == "__main__":
    unittest.main()
