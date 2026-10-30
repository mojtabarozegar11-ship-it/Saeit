"""S-01 degraded GET audit regression; runs without Django or a database."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


class RequestAuditDegradedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_models = types.ModuleType("core.models")
        cls.audit_create = MagicMock()
        fake_models.AuditLog = types.SimpleNamespace(objects=types.SimpleNamespace(create=cls.audit_create))
        path = Path(__file__).resolve().parents[1] / "core" / "middleware.py"
        spec = importlib.util.spec_from_file_location("core._s01_degraded_middleware_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"core.models": fake_models}):
            spec.loader.exec_module(module)
        cls.middleware_type = module.RequestAuditMiddleware

    def setUp(self):
        self.audit_create.reset_mock()

    def call(self, method="GET", status=503, marker=True, authenticated=True):
        response = {"X-ZM-Data-Status": "temporarily-unavailable"} if marker else {}
        class Response(dict):
            pass
        result = Response(response)
        result.status_code = status
        request = types.SimpleNamespace(method=method, path="/academy/",
            user=types.SimpleNamespace(is_authenticated=authenticated, pk=7))
        output = self.middleware_type(lambda req: result)(request)
        self.assertIs(output, result)
        self.assertTrue(getattr(request, "trace_id", None))
        return self.audit_create.call_count

    def test_get_degraded_does_not_write(self):
        self.assertEqual(self.call(), 0)

    def test_head_degraded_does_not_write(self):
        self.assertEqual(self.call(method="HEAD"), 0)

    def test_post_degraded_preserves_mutation_audit(self):
        self.assertEqual(self.call(method="POST"), 1)

    def test_successful_get_preserves_audit(self):
        self.assertEqual(self.call(status=200, marker=False), 1)

    def test_unmarked_503_preserves_audit(self):
        self.assertEqual(self.call(status=503, marker=False), 1)

    def test_anonymous_degraded_never_writes(self):
        self.assertEqual(self.call(authenticated=False), 0)

    def test_audit_error_does_not_break_response(self):
        self.audit_create.side_effect = RuntimeError("synthetic unavailable DB")
        try:
            self.assertEqual(self.call(status=200, marker=False), 1)
        finally:
            self.audit_create.side_effect = None


if __name__ == "__main__":
    unittest.main()
