"""Isolated source-backed checkout email safety tests; no production effects.

These tests exercise the real helper source without loading Django or a database.
They validate input/identity boundaries, not mainnet payment or email ownership.
"""
import ast
import hmac
import sys
import tempfile
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


def source_function(name, injected=None, source=SOURCE):
    parsed = ast.parse(source.read_text(encoding="utf8"))
    node = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {"Http404": Http404, "hmac": hmac}
    namespace.update(injected or {})
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
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

    def test_signed_in_account_with_matching_email_may_start_invoice(self):
        self.user = types.SimpleNamespace(username="existing_account", email="alice@Buyer.ORG")
        self.assertIs(self.dispatch(request_values("alice@buyer.org"), self.view, (), {},
                                    create=True), self.response)

    def test_signed_in_account_cannot_start_invoice_without_email(self):
        self.user = types.SimpleNamespace(username="existing_account", email="alice@buyer.org")
        with self.assertRaises(Http404):
            self.dispatch(request_values(), self.view, (), {}, create=True)
        self.view.assert_not_called()

    def test_signed_in_account_cannot_buy_with_unrelated_email(self):
        self.user = types.SimpleNamespace(username="existing_account", email="alice@buyer.org")
        with self.assertRaises(Http404):
            self.dispatch(request_values("other@buyer.org"), self.view, (), {}, create=True)
        self.view.assert_not_called()

    def test_signed_in_account_without_stored_email_cannot_buy(self):
        self.user = types.SimpleNamespace(username="existing_account", email="")
        with self.assertRaises(Http404):
            self.dispatch(request_values("alice@buyer.org"), self.view, (), {}, create=True)
        self.view.assert_not_called()



class CheckoutReleaseFormTests(unittest.TestCase):
    """Reject a live release if the rendered checkout lacks its buyer email input."""

    def setUp(self):
        release = SOURCE.parents[1] / "scripts/mpw_guest_checkout_live_release.py"
        self.check = source_function("has_buyer_email_form", source=release)

    def test_accepts_required_email_in_post_form(self):
        self.assertTrue(self.check(
            '<form method="POST" action="/invoice/start/">'
            '<input name="email" type="email" required></form>'
        ))

    def test_rejects_missing_email_field(self):
        self.assertFalse(self.check(
            '<form method="POST"><input name="name" required></form>'
        ))

    def test_rejects_disabled_field(self):
        self.assertFalse(self.check(
            '<form method="post"><input type="email" name="email" required disabled></form>'
        ))

    def test_rejects_email_outside_post_form(self):
        self.assertFalse(self.check(
            '<input type="email" name="email" required>'
            '<form method="GET"><input type="email" name="email" required></form>'
        ))

    def test_rejects_optional_or_non_email_input(self):
        for html in (
            '<form method="post"><input type="email" name="email"></form>',
            '<form method="post"><input type="text" name="email" required></form>',
        ):
            with self.subTest(html=html):
                self.assertFalse(self.check(html))

    def test_rendered_checkout_requires_exact_product_action(self):
        markup = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                  '<input type="email" name="email" required></form>')
        self.assertTrue(self.check(markup,
                                   expected_action="/commerce/trx-easy/start/72/"))
        self.assertFalse(self.check(markup,
                                    expected_action="/commerce/trx-easy/start/225/"))

    def test_rejects_external_or_wrong_action_on_rendered_checkout(self):
        for action in ("https://unknown.example/start/72/",
                       "/commerce/trx-easy/status/72/", "/store/"):
            markup = ('<form method="post" action="' + action + '">'
                      '<input type="email" name="email" required></form>')
            with self.subTest(action=action):
                self.assertFalse(self.check(
                    markup, expected_action="/commerce/trx-easy/start/72/"))


class CheckoutSourcePreflightTests(unittest.TestCase):
    """Temporary files only; never touch production hosting."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mpw-email-gate-")
        self.addCleanup(self.temp.cleanup)
        self.app = Path(self.temp.name)
        self.template = (self.app / "mpw_commerce" / "templates" /
                         "mpw_commerce" / "product_checkout.html")
        self.template.parent.mkdir(parents=True)
        release = SOURCE.parents[1] / "scripts/mpw_guest_checkout_live_release.py"
        self.html_check = source_function("has_buyer_email_form", source=release)
        self.preflight = source_function(
            "preflight_checkout_email_template",
            injected={
                "APP": self.app,
                "has_buyer_email_form": self.html_check,
                "fail": lambda message: (_ for _ in ()).throw(RuntimeError(message))
            },
            source=release,
        )

    def test_preflight_blocks_missing_template(self):
        with self.assertRaisesRegex(RuntimeError, "CHECKOUT_TEMPLATE_MISSING_OR_UNSAFE"):
            self.preflight()

    def test_preflight_blocks_form_without_email(self):
        self.template.write_text(
            '<form method="post"><button>Buy</button></form>', encoding="utf8")
        with self.assertRaisesRegex(RuntimeError, "GUEST_EMAIL_TEMPLATE_CONTRACT_MISSING"):
            self.preflight()

    def test_preflight_accepts_source_contract(self):
        self.template.write_text(
            '<form method="POST" action="/commerce/trx-easy/start/72/">'
            '<input name="email" type="email" required>'
            '<button>Create invoice and pay with TRX</button></form>', encoding="utf8")
        self.assertTrue(self.preflight())

    def test_preflight_rejects_symlink(self):
        external = self.app / "external-template.html"
        external.write_text(
            '<form method="post"><input type="email" name="email" required></form>',
            encoding="utf8")
        self.template.symlink_to(external)
        with self.assertRaisesRegex(RuntimeError, "CHECKOUT_TEMPLATE_MISSING_OR_UNSAFE"):
            self.preflight()

    def test_preflight_rejects_oversized_template(self):
        self.template.write_text("X" * 180001, encoding="utf8")
        with self.assertRaisesRegex(RuntimeError, "CHECKOUT_TEMPLATE_OVERSIZE"):
            self.preflight()


if __name__ == "__main__":
    unittest.main()
