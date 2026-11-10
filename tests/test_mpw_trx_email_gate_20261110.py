"""New-invoice email contract, isolated from Django DB and paid orders."""
import ast
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_guest_commerce.py"


class MissingBuyerEmail(Exception):
    pass


class InvalidEmail(Exception):
    pass


def source_function(name, namespace):
    tree = ast.parse(SOURCE.read_text(encoding="utf8"))
    node = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = dict(namespace)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), scope)
    return scope[name]


def request_with_emails(*values):
    return SimpleNamespace(POST=SimpleNamespace(getlist=lambda name: (
        list(values) if name == "email" else [])))


def fake_validator_modules(callback):
    names = ("django", "django.core", "django.core.exceptions",
             "django.core.validators")
    modules = {name: types.ModuleType(name) for name in names}
    modules["django.core.exceptions"].ValidationError = InvalidEmail
    modules["django.core.validators"].validate_email = callback
    return modules


class NewPurchaseEmailContract(unittest.TestCase):
    def test_valid_submitted_email_is_validated_before_use(self):
        validator = Mock()
        with patch.dict(sys.modules, fake_validator_modules(validator)):
            verify = source_function("_require_buyer_email", {"Http404": MissingBuyerEmail})
            self.assertEqual(verify(request_with_emails("buyer@example.com")),
                             "buyer@example.com")
        validator.assert_called_once_with("buyer@example.com")

    def test_alternate_checkout_emails_cannot_override_required_email(self):
        for alias in ("buyer_email", "customer_email", "purchaser_email",
                      "purchase_email"):
            for payload in (["other@example.com"], [""]):
                with self.subTest(alias=alias, value=payload):
                    posted = {"email": ["buyer@example.com"], alias: payload}
                    request = SimpleNamespace(POST=SimpleNamespace(
                        getlist=lambda name: posted.get(name, [])))
                    validator = Mock()
                    with patch.dict(sys.modules, fake_validator_modules(validator)):
                        verify = source_function("_require_buyer_email",
                                                 {"Http404": MissingBuyerEmail})
                        with self.assertRaises(MissingBuyerEmail):
                            verify(request)
                    validator.assert_not_called()

    def test_missing_duplicate_or_blank_email_is_rejected(self):
        for values in ((), ("",), ("a@example.com", "b@example.com")):
            with self.subTest(values=values):
                validator = Mock()
                with patch.dict(sys.modules, fake_validator_modules(validator)):
                    verify = source_function("_require_buyer_email",
                                             {"Http404": MissingBuyerEmail})
                    with self.assertRaises(MissingBuyerEmail):
                        verify(request_with_emails(*values))
                validator.assert_not_called()

    def test_surrounding_space_and_overlong_email_are_rejected(self):
        for email in (" buyer@example.com", "buyer@example.com ",
                      "x" * 250 + "@example.com"):
            with self.subTest(email=email[:32]):
                validator = Mock()
                with patch.dict(sys.modules, fake_validator_modules(validator)):
                    verify = source_function("_require_buyer_email",
                                             {"Http404": MissingBuyerEmail})
                    with self.assertRaises(MissingBuyerEmail):
                        verify(request_with_emails(email))
                validator.assert_not_called()

    def test_django_validator_rejection_fails_closed(self):
        validator = Mock(side_effect=InvalidEmail("bad address"))
        with patch.dict(sys.modules, fake_validator_modules(validator)):
            verify = source_function("_require_buyer_email",
                                     {"Http404": MissingBuyerEmail})
            with self.assertRaises(MissingBuyerEmail):
                verify(request_with_emails("not-an-email"))
        validator.assert_called_once_with("not-an-email")

    def test_new_sale_invalid_email_does_not_create_guest_or_invoice(self):
        rights = Mock()
        email = Mock(side_effect=MissingBuyerEmail("missing"))
        identity = Mock()
        invoice = Mock()
        dispatch = source_function("_dispatch", {
            "_host_ok": lambda request: True,
            "_require_new_sale_rights": rights,
            "_require_buyer_email": email,
            "_identity": identity,
            "_install_cookie": Mock(),
            "Http404": MissingBuyerEmail,
        })
        req = request_with_emails()
        with self.assertRaises(MissingBuyerEmail):
            dispatch(req, invoice, (), {"product_id": 72},
                     create=True, require_new_sale=True)
        rights.assert_called_once_with(72)
        email.assert_called_once_with(req)
        identity.assert_not_called()
        invoice.assert_not_called()

    def test_valid_email_delegates_to_durable_order_binding(self):
        # No invoice is created by this isolated test: the host recovery
        # service owns the atomic GuestOrderEmail claim and invoice mapping.
        identity = Mock()
        invoice = Mock()
        installer = Mock()
        bound = Mock(return_value="bound-invoice-response")
        recovery = types.ModuleType("services.mpw_trx_email_recovery")
        recovery.bound_checkout = bound
        rights = Mock()
        email = Mock(return_value="buyer@example.com")
        dispatch = source_function("_dispatch", {
            "_host_ok": lambda request: True,
            "_require_new_sale_rights": rights,
            "_require_buyer_email": email,
            "_identity": identity,
            "_install_cookie": installer,
            "Http404": MissingBuyerEmail,
        })
        req = request_with_emails("buyer@example.com")
        with patch.dict(sys.modules, {
            "services": types.ModuleType("services"),
            "services.mpw_trx_email_recovery": recovery,
        }):
            result = dispatch(req, invoice, (), {"product_id": 72},
                              create=True, require_new_sale=True)
        self.assertEqual(result, "bound-invoice-response")
        rights.assert_called_once_with(72)
        email.assert_called_once_with(req)
        bound.assert_called_once_with(
            req, invoice, identity, installer, (), {"product_id": 72})
        identity.assert_not_called()
        invoice.assert_not_called()

    def test_missing_order_binding_service_blocks_new_invoice(self):
        guest = Mock()
        invoice = Mock()
        dispatch = source_function("_dispatch", {
            "_host_ok": lambda request: True,
            "_require_new_sale_rights": Mock(),
            "_require_buyer_email": Mock(return_value="buyer@example.com"),
            "_identity": guest,
            "_install_cookie": Mock(),
            "Http404": MissingBuyerEmail,
        })
        req = request_with_emails("buyer@example.com")
        with patch.dict(sys.modules, {"services.mpw_trx_email_recovery": None}):
            with self.assertRaisesRegex(
                    MissingBuyerEmail, "Email-bound checkout is unavailable"):
                dispatch(req, invoice, (), {"product_id": 72},
                         create=True, require_new_sale=True)
        guest.assert_not_called()
        invoice.assert_not_called()

    def test_paid_invoice_recovery_does_not_require_email_again(self):
        identity = Mock(return_value=(SimpleNamespace(), "existing-token"))
        invoice = Mock(return_value="existing-invoice")
        email = Mock(side_effect=AssertionError("Email gate must not run on recovery"))
        rights = Mock(side_effect=AssertionError("Rights gate must not run on recovery"))
        dispatch = source_function("_dispatch", {
            "_host_ok": lambda request: True,
            "_require_new_sale_rights": rights,
            "_require_buyer_email": email,
            "_identity": identity,
            "_install_cookie": lambda response, token: (response, token),
            "Http404": MissingBuyerEmail,
        })
        req = SimpleNamespace()
        self.assertEqual(dispatch(req, invoice, (), {"invoice_id": 49}),
                         ("existing-invoice", "existing-token"))
        rights.assert_not_called()
        email.assert_not_called()
        invoice.assert_called_once_with(req, invoice_id=49)


if __name__ == "__main__":
    unittest.main()
