"""Isolated source-backed checkout email safety tests; no production effects.

These tests exercise the real helper source without loading Django or a database.
They validate input/identity boundaries, not mainnet payment or email ownership.
"""
import ast
import hashlib
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
            '<form method="POST" action="/commerce/trx-easy/start/72/">'
            '<input name="email" type="email" required></form>'
        ))

    def test_rejects_missing_email_field(self):
        self.assertFalse(self.check(
            '<form method="POST" action="/commerce/trx-easy/start/72/">'
            '<input name="name" required></form>'
        ))

    def test_rejects_disabled_field(self):
        self.assertFalse(self.check(
            '<form method="post" action="/commerce/trx-easy/start/72/">'
            '<input type="email" name="email" required disabled></form>'
        ))

    def test_rejects_email_outside_post_form(self):
        self.assertFalse(self.check(
            '<input type="email" name="email" required>'
            '<form method="GET" action="/commerce/trx-easy/start/72/">'
            '<input type="email" name="email" required></form>'
        ))

    def test_rejects_optional_or_non_email_input(self):
        for html in (
            '<form method="post" action="/commerce/trx-easy/start/72/">'
            '<input type="email" name="email"></form>',
            '<form method="post" action="/commerce/trx-easy/start/72/">'
            '<input type="text" name="email" required></form>',
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

    def test_rejects_duplicate_email_controls(self):
        markup = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                  '<input type="email" name="email" required>'
                  '<input type="email" name="email" required></form>')
        self.assertFalse(self.check(markup))

    def test_rejects_disabled_fieldset_and_hidden_email(self):
        for html in (
            '<fieldset disabled><input type="email" name="email" required></fieldset>',
            '<input type="email" name="email" required hidden>',
            '<input type="email" name="email" required aria-hidden="true">',
            '<input type="email" name="email" required style="display: none">',
        ):
            markup = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                      + html + '</form>')
            with self.subTest(html=html):
                self.assertFalse(self.check(markup))

    def test_rejects_invalid_invoice_action_paths(self):
        for action in (
            "/commerce/trx-easy/start/0/",
            "/commerce/trx-easy/start/72/../../evil",
            "/commerce/trx-easy/start/72/?to=another",
            "//attacker.com/commerce/trx-easy/start/72/",
        ):
            markup = ('<form method="post" action="' + action + '">'
                      '<input type="email" name="email" required></form>')
            with self.subTest(action=action):
                self.assertFalse(self.check(markup))

    def test_rendered_form_requires_csrf_in_same_form(self):
        valid = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                 '<input type="hidden" name="csrfmiddlewaretoken" value="' 
                 + "A"*64 + '">'
                 '<input type="email" name="email" required></form>')
        self.assertTrue(self.check(valid, require_csrf=True))
        self.assertFalse(self.check(
            valid.replace('name="csrfmiddlewaretoken"', 'name="not_csrf"'),
            require_csrf=True))
        with_other = ('<form method="post" action="/commerce/trx-easy/start/73/">'
                      '<input type="hidden" name="csrfmiddlewaretoken" value="' 
                      + "A"*64 + '"></form>'
                      '<form method="post" action="/commerce/trx-easy/start/72/">'
                      '<input name="email" type="email" required></form>')
        self.assertFalse(self.check(
            with_other, expected_action="/commerce/trx-easy/start/72/",
            require_csrf=True))

    def test_source_csrf_must_be_inside_invoice_form(self):
        markup = ('<form method="post" action="/newsletter/">'
                  '{% csrf_token %}</form>'
                  '<form method="post" action="/commerce/trx-easy/start/72/">'
                  '<input type="email" name="email" required></form>')
        self.assertFalse(self.check(markup, require_source_csrf=True))
        self.assertTrue(self.check(
            markup.replace('<input type="email"', '{% csrf_token %}<input type="email"'),
            require_source_csrf=True))


    def test_rejects_short_blank_or_duplicate_rendered_csrf(self):
        form_open = '<form method="post" action="/commerce/trx-easy/start/72/">'
        email = '<input type="email" name="email" required>'
        csrf = lambda val: ('<input type="hidden" name="csrfmiddlewaretoken" '
                            'value="' + val + '">')
        for val in ("", "short", " " * 64):
            with self.subTest(value=repr(val)):
                self.assertFalse(self.check(form_open + csrf(val) + email + '</form>',
                                            require_csrf=True))
        self.assertFalse(self.check(
            form_open + csrf("A"*64) + csrf("B"*64) + email + '</form>',
            require_csrf=True))

    def test_rejects_csrf_token_outside_invoice_form(self):
        markup = ('<form method="post" action="/commerce/trx-easy/start/73/">'
                  '<input type="hidden" name="csrfmiddlewaretoken" value="' +
                  "A"*64 + '"></form>'
                  '<form method="post" action="/commerce/trx-easy/start/72/">'
                  '<input type="email" name="email" required></form>')
        self.assertFalse(self.check(markup,
                                    expected_action="/commerce/trx-easy/start/72/",
                                    require_csrf=True))

    def test_source_allows_only_product_id_or_pk_placeholders(self):
        for variable in ("{{ product.pk }}", "{{product.id}}"):
            form = ('<form method="post" action="/commerce/trx-easy/start/'
                    + variable + '/">{% csrf_token %}'
                    '<input type="email" name="email" required></form>')
            with self.subTest(variable=variable):
                self.assertTrue(self.check(form, require_source_csrf=True))
                self.assertFalse(self.check(form, require_csrf=True))
        for variable in ("{{ user.id }}", "{{ product.slug }}", "{{ next }}"):
            form = ('<form method="post" action="/commerce/trx-easy/start/'
                    + variable + '/">{% csrf_token %}'
                    '<input type="email" name="email" required></form>')
            with self.subTest(variable=variable):
                self.assertFalse(self.check(form, require_source_csrf=True))



    def test_rejects_source_csrf_inside_script(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<input type="email" name="email" required>'
                '<script>{% csrf_token %}</script></form>')
        self.assertFalse(self.check(html, require_source_csrf=True))

    def test_rejects_source_csrf_inside_textarea(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<input type="email" name="email" required>'
                '<textarea>{% csrf_token %}</textarea></form>')
        self.assertFalse(self.check(html, require_source_csrf=True))

    def test_rejects_rendered_csrf_inside_disabled_fieldset(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<input type="email" name="email" required>'
                '<fieldset disabled><input type="hidden" name="csrfmiddlewaretoken" value="'
                + "A" * 64 + '"></fieldset></form>')
        self.assertFalse(self.check(html, require_csrf=True))

    def test_rejects_email_in_hidden_ancestor(self):
        for ancestor in ('<div hidden>', '<div style="display: none">',
                         '<section aria-hidden="true">', '<section style="opacity:0">'):
            closing = '</div>' if ancestor.startswith('<div') else '</section>'
            html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                    + ancestor + '<input name="email" type="email" required>'
                    + closing + '</form>')
            with self.subTest(ancestor=ancestor):
                self.assertFalse(self.check(html))

    def test_rejects_readonly_email(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<input name="email" type="email" required readonly></form>')
        self.assertFalse(self.check(html))

    def test_rejects_nested_invoice_forms(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<form method="post" action="/commerce/trx-easy/start/72/">'
                '<input type="email" name="email" required>'
                '</form></form>')
        self.assertFalse(self.check(html))

    def test_rejects_token_in_template_element(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<input name="email" type="email" required>'
                '<template>{% csrf_token %}</template></form>')
        self.assertFalse(self.check(html, require_source_csrf=True))

    def test_rejects_controls_inside_select_or_button(self):
        for tag in ("select", "button"):
            html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                    '<' + tag + '><input name="email" type="email" required></' + tag + '>'
                    '</form>')
            with self.subTest(tag=tag):
                self.assertFalse(self.check(html))

    def test_rejects_two_eligible_checkout_forms(self):
        single = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                  '<input name="email" type="email" required></form>')
        self.assertFalse(self.check(single + single))

    def test_rejects_duplicate_source_csrf_tokens_in_one_form(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '{% csrf_token %}{% csrf_token %}'
                '<input name="email" type="email" required></form>')
        self.assertFalse(self.check(html, require_source_csrf=True))



    def test_form_itself_cannot_be_hidden(self):
        html = ('<form hidden method="post" action="/commerce/trx-easy/start/72/">'
                '<input name="email" type="email" required></form>')
        self.assertFalse(self.check(html))

    def test_form_style_display_none_fails_closed(self):
        html = ('<form style="display:none" method="post" '
                'action="/commerce/trx-easy/start/72/">'
                '<input name="email" type="email" required></form>')
        self.assertFalse(self.check(html))

    def test_checkout_in_hidden_parent_is_not_eligible(self):
        html = ('<div hidden><form method="post" '
                'action="/commerce/trx-easy/start/72/">'
                '<input name="email" type="email" required></form></div>')
        self.assertFalse(self.check(html))

    def test_checkout_in_aria_hidden_ancestor_is_not_eligible(self):
        html = ('<section aria-hidden="true"><form method="post" '
                'action="/commerce/trx-easy/start/72/">'
                '<input name="email" type="email" required></form></section>')
        self.assertFalse(self.check(html))

    def test_checkout_in_inert_ancestor_is_not_eligible(self):
        html = ('<div inert><form method="post" '
                'action="/commerce/trx-easy/start/72/">'
                '<input name="email" type="email" required></form></div>')
        self.assertFalse(self.check(html))

    def test_checkout_in_disabled_ancestor_fieldset_fails_closed(self):
        html = ('<fieldset disabled><form method="post" '
                'action="/commerce/trx-easy/start/72/">'
                '<input name="email" type="email" required></form></fieldset>')
        self.assertFalse(self.check(html))

    def test_buyer_email_must_not_override_form_owner(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<input name="email" type="email" required form="other"></form>')
        self.assertFalse(self.check(html))

    def test_csrf_must_not_override_form_owner(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<input name="email" type="email" required>'
                '<input type="hidden" name="csrfmiddlewaretoken" form="other" '
                'value="' + "A" * 64 + '"></form>')
        self.assertFalse(self.check(html, require_csrf=True))

    def test_email_inside_datalist_is_not_submittable(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<datalist><input name="email" type="email" required>'
                '</datalist></form>')
        self.assertFalse(self.check(html))

    def test_select_named_email_invalidates_sole_email_gate(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<input name="email" type="email" required>'
                '<select name="email"><option value="x">X</option></select>'
                '</form>')
        self.assertFalse(self.check(html))

    def test_textarea_named_csrf_invalidates_sole_csrf_gate(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<input name="email" type="email" required>'
                '<input type="hidden" name="csrfmiddlewaretoken" value="' +
                "A" * 64 + '"><textarea name="csrfmiddlewaretoken">x</textarea>'
                '</form>')
        self.assertFalse(self.check(html, require_csrf=True))

    def test_valid_form_with_semantic_container_passes(self):
        html = ('<main><section><form method="post" '
                'action="/commerce/trx-easy/start/72/">'
                '<input name="email" type="email" required>'
                '<input type="hidden" name="csrfmiddlewaretoken" value="' +
                "A" * 64 + '"></form></section></main>')
        self.assertTrue(self.check(
            html, expected_action="/commerce/trx-easy/start/72/",
            require_csrf=True))


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
                "digest": lambda raw: hashlib.sha256(raw).hexdigest(),
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

    def test_preflight_rejects_unrelated_email_newsletter_form(self):
        self.template.write_text(
            '<form method="post" action="/newsletter/subscribe/">'
            '<input type="email" name="email" required></form>',
            encoding="utf8")
        with self.assertRaisesRegex(RuntimeError, "GUEST_EMAIL_TEMPLATE_CONTRACT_MISSING"):
            self.preflight()

    def test_preflight_accepts_source_contract(self):
        self.template.write_text(
            '<form method="POST" action="/commerce/trx-easy/start/72/">'
            '{% csrf_token %}<input name="email" type="email" required>'
            '<button>Create invoice and pay with TRX</button></form>', encoding="utf8")
        self.assertEqual(self.preflight(),
                         hashlib.sha256(self.template.read_bytes()).hexdigest())

    def test_preflight_rejects_missing_source_csrf(self):
        self.template.write_text(
            '<form method="post" action="/commerce/trx-easy/start/72/">'
            '<input name="email" type="email" required></form>', encoding="utf8")
        with self.assertRaisesRegex(RuntimeError, "GUEST_EMAIL_TEMPLATE_CONTRACT_MISSING"):
            self.preflight()

    def test_preflight_rejects_parent_symlink(self):
        external_dir = self.app / "external-dir"
        external_dir.mkdir()
        (external_dir / "product_checkout.html").write_text(
            '<form method="post" action="/commerce/trx-easy/start/72/">'
            '{% csrf_token %}<input name="email" type="email" required></form>',
            encoding="utf8")
        self.template.parent.rmdir()
        self.template.parent.symlink_to(external_dir, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "CHECKOUT_TEMPLATE_PARENT_SYMLINK"):
            self.preflight()

    def test_preflight_requires_correct_source_action(self):
        self.template.write_text(
            '<form method="post" action="/newsletter/subscribe/">'
            '{% csrf_token %}<input name="email" type="email" required></form>',
            encoding="utf8")
        with self.assertRaisesRegex(RuntimeError, "GUEST_EMAIL_TEMPLATE_CONTRACT_MISSING"):
            self.preflight()

    def test_preflight_accepts_canonical_django_product_placeholder(self):
        self.template.write_text(
            '<form method="post" action="/commerce/trx-easy/start/{{ product.pk }}/">'
            '{% csrf_token %}<input name="email" type="email" required>'
            '</form>', encoding="utf8")
        self.assertEqual(self.preflight(),
                         hashlib.sha256(self.template.read_bytes()).hexdigest())

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
