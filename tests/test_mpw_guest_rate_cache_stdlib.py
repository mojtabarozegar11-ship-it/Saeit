"""No-Django regression tests for guest rate-limit cache configuration.

Run: python -m unittest discover -s tests -p test_mpw_guest_rate_cache_stdlib.py
This checks the exact production function using AST extraction; it is not
a substitute for Django, shared-cache, or concurrent HTTP integration tests.
"""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace


class Http404(Exception):
    pass


SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_guest_commerce.py"
tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name == "_assert_usable_guest_cache"]
if len(functions) != 1:
    raise RuntimeError("Exactly one guest cache guard required")
scope = {"Http404": Http404}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), scope)
guard = scope["_assert_usable_guest_cache"]


class GuestRateCacheTests(unittest.TestCase):
    def test_dummy_cache_rejected(self):
        bad = SimpleNamespace(CACHES={"default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
        with self.assertRaisesRegex(Http404, "not operational"):
            guard(bad)

    def test_missing_backend_rejected(self):
        for bad in (SimpleNamespace(CACHES={}), SimpleNamespace(CACHES={"default": {}}),
                    SimpleNamespace(CACHES={"default": {"BACKEND": ""}})):
            with self.subTest(bad=bad), self.assertRaises(Http404):
                guard(bad)

    def test_locmem_config_not_falsely_rejected(self):
        configured = SimpleNamespace(CACHES={"default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
        self.assertIsNone(guard(configured))

    def test_redis_config_not_falsely_rejected(self):
        configured = SimpleNamespace(CACHES={"default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache"}})
        self.assertIsNone(guard(configured))


if __name__ == "__main__":
    unittest.main()
