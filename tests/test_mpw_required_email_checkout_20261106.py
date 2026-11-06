"""Offline behavioral checks for email-required, no-registration checkout."""
from __future__ import annotations

import ast
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "services/mpw_trx_guest_commerce.py"


class Http404(Exception):
    pass


class ValidationError(Exception):
    pass


def validate_email(value):
    if len(value) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValidationError(value)


class POST:
    def __init__(self, **values):
        self.values = values

    def getlist(self, key):
        raw = self.values.get(key, [])
        return raw if isinstance(raw, list) else [raw]


class CheckoutEmail(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_text("utf-8"))
        wanted = {"_required_checkout_email", "_identity"}
        selected = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name in wanted]
        self.assertEqual({fn.name for fn in selected}, wanted)
        validators = ModuleType("django.core.validators")
        validators.validate_email = validate_email
        errors = ModuleType("django.core.exceptions")
        errors.ValidationError = ValidationError
        self.modules = patch.dict(sys.modules, {
            "django": ModuleType("django"),
            "django.core": ModuleType("django.core"),
            "django.core.validators": validators,
            "django.core.exceptions": errors,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.space = {
            "Http404": Http404, "_host_ok": lambda request: True,
            "_read_user": lambda request: None,
            "_new_user": lambda request: (SimpleNamespace(username="mpwguest_abc"), "guest-cookie"),
        }
        code = compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec")
        exec(code, self.space)
        self.identity = self.space["_identity"]

    def request(self, user=None, **fields):
        return SimpleNamespace(POST=POST(**fields), user=user)

    def test_guest_requires_no_registered_account(self):
        user, token = self.identity(self.request(email="buyer@example.org"), create=True)
        self.assertEqual(user.username, "mpwguest_abc")
        self.assertEqual(token, "guest-cookie")

    def test_missing_and_blank_email_rejected(self):
        for fields in ({}, {"email": ""}, {"email": "   "}):
            with self.subTest(fields=fields), self.assertRaises(Http404):
                self.identity(self.request(**fields), create=True)

    def test_malformed_and_oversized_email_rejected(self):
        for address in ("buyer", "a@b", "a @example.org", "a" * 255 + "@b.co"):
            with self.subTest(address=address[:18]), self.assertRaises(Http404):
                self.identity(self.request(email=address), create=True)

    def test_conflicting_emails_rejected_even_if_one_valid(self):
        with self.assertRaises(Http404):
            self.identity(self.request(email="a@example.org", buyer_email="b@example.org"), create=True)

    def test_identical_case_insensitive_aliases_allowed(self):
        user, _ = self.identity(self.request(email=" Me@Example.ORG ", buyer_email="me@example.org"), create=True)
        self.assertTrue(user.username.startswith("mpwguest_"))

    def test_authenticated_account_email_is_still_required(self):
        account = SimpleNamespace(is_authenticated=True, email="member@example.org")
        for fields in ({}, {"email": "other@example.org"}, {"email": "invalid"}):
            with self.subTest(fields=fields), self.assertRaises(Http404):
                self.identity(self.request(user=account, **fields), create=True)
        user, token = self.identity(self.request(user=account, email="MEMBER@example.org"), create=True)
        self.assertIs(user, account)
        self.assertIsNone(token)


if __name__ == "__main__":
    unittest.main()
