"""Isolated source-backed checkout email safety tests; no production effects.

These tests exercise the real helper source without loading Django or a database.
They validate input/identity boundaries, not mainnet payment or email ownership.
"""
import ast
import hmac
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_guest_commerce.py"


class Http404(Exception):
    pass


class ValidationError(Exception):
    pass


def fake_django():
    modules = {name: types.ModuleType(name) for name in (
        "django", "django.core", "django.core.exceptions",
        "django.core.validators",
    )}

    def validate_email(value):
        local, sep, domain = value.rpartition("@")
        if (not sep or not local or "." not in domain or domain.startswith(".")
                or domain.endswith(".") or ".." in domain
                or not all(part for part in domain.split("."))):
            raise ValidationError("invalid email")
    modules["django.core.exceptions"].ValidationError = ValidationError
    modules["django.core.validators"].validate_email = validate_email
    return modules


def source_function(name, injected=None):
    parsed = ast.parse(SOURCE.read_text(encoding="utf8"))
    node = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {"Http404": Http404, "hmac": hmac}
    namespace.update(injected or {})
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace[name]


def request_values(*values):
    return types.SimpleNamespace(
        POST=types.SimpleNamespace(getlist=lambda key: list(values) if key == "email" else [])
    )


class GuestEmailPolicyTests(unittest.TestCase):
    def setUp(self):
        self.fn = source_function("_buyer_email")
        self.modules = fake_django()
        self.scope = patch.dict(sys.modules, self.modules)
        self.scope.__enter__()

    def tearDown(self):
        self.scope.__exit__(None, None, None)

    def test_accepts_email_and_normalizes_domain_only(self):
        self.assertEqual(self.fn(request_values("Alice+1@Buyer.ORG")), "Alice+1@buyer.org")

    def test_rejects_missing_and_duplicate_email(self):
        for values in ((), ("a@b.org", "a@b.org")):
            with self.subTest(values=values), self.assertRaises(Http404):
                self.fn(request_values(*values))

    def test_rejects_nontext_and_oversized_email(self):
        for value in (None, 3, "x" * 250 + "@buyer.org"):
            with self.subTest(value=str(value)[:30]), self.assertRaises(Http404):
                self.fn(request_values(value))

    def test_rejects_whitespace_control_newline(self):
        for value in (" abc@buyer.org", "a@buyer.org ", "a@buy\ner.org", "a\t@buyer.org"):
            with self.subTest(value=repr(value)), self.assertRaises(Http404):
                self.fn(request_values(value))

    def test_rejects_nonascii_email_until_eai_support_exists(self):
        with self.assertRaises(Http404):
            self.fn(request_values("mø@testdomain.org"))

    def test_rejects_reserved_internal_and_example_domains(self):
        for value in ("a@guest.mojplaywin.com", "a@foo.guest.mojplaywin.com",
                      "a@example.com", "a@test.example.org", "a@domain.invalid",
                      "a@demo.test", "a@localhost"):
            with self.subTest(value=value), self.assertRaises(Http404):
                self.fn(request_values(value))

    def test_rejects_malformed_email(self):
        for value in ("invalid", "@buyer.org", "a@", "a@buyer", "a@@buyer.org"):
            with self.subTest(value=value), self.assertRaises(Http404):
                self.fn(request_values(value))


class GuestInvoiceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.modules = fake_django()
        self.scope = patch.dict(sys.modules, self.modules)
        self.scope.__enter__()
        email_fn = source_function("_buyer_email")
        self.response = object()
        self.view = Mock(return_value=self.response)
        self.user = types.SimpleNamespace(username="mpwguest_abc", email="alice@buyer.org")
        self.dispatch = source_function("_dispatch", {
            "_buyer_email": email_fn,
            "_identity": lambda request, create=False: (self.user, None),
            "_install_cookie": lambda response, token: response,
        })

    def tearDown(self):
        self.scope.__exit__(None, None, None)

    def test_same_guest_email_allows_invoice_call(self):
        req = request_values("alice@buyer.org")
        self.assertIs(self.dispatch(req, self.view, (), {}, create=True), self.response)
        self.view.assert_called_once()
        self.assertIs(req.user, self.user)

    def test_changed_guest_email_blocks_invoice_call(self):
        with self.assertRaises(Http404):
            self.dispatch(request_values("victim@buyer.org"), self.view, (), {}, create=True)
        self.view.assert_not_called()

    def test_missing_email_blocks_cookie_reuse(self):
        with self.assertRaises(Http404):
            self.dispatch(request_values(), self.view, (), {}, create=True)
        self.view.assert_not_called()

    def test_download_path_does_not_rebind_email(self):
        req = request_values()
        self.assertIs(self.dispatch(req, self.view, (), {}, create=False), self.response)
        self.assertEqual(self.user.email, "alice@buyer.org")

    def test_signed_in_non_guest_retains_existing_flow(self):
        self.user = types.SimpleNamespace(username="existing_account", email="alice@buyer.org")
        self.assertIs(self.dispatch(request_values(), self.view, (), {}, create=True),
                      self.response)


if __name__ == "__main__":
    unittest.main()
