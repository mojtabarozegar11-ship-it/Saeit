"""No-network regression tests for signed TRX guest privilege isolation."""
from __future__ import annotations

import ast
from contextlib import nullcontext
from pathlib import Path
import secrets
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_guest_commerce.py"


class Http404(Exception):
    pass


class BadSignature(Exception):
    pass


class SignatureExpired(BadSignature):
    pass


class GuestOwnerPrivilegeGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_text("utf-8"))
        selected = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name in {"_read_user", "_new_user"}]
        assert len(selected) == 2
        cls.code = compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec")

    def setUp(self):
        self.principal = None
        model = SimpleNamespace(USERNAME_FIELD="username")
        model._meta = SimpleNamespace(get_field=lambda name: SimpleNamespace(unique=True))
        model.objects = SimpleNamespace(filter=lambda **kwargs: SimpleNamespace(
            first=lambda: self.principal))
        auth = ModuleType("django.contrib.auth")
        auth.get_user_model = lambda: model
        database = ModuleType("django.db")
        database.IntegrityError = type("IntegrityError", (Exception,), {})
        database.transaction = SimpleNamespace(atomic=lambda: None)
        self.modules = patch.dict(sys.modules, {
            "django": ModuleType("django"),
            "django.contrib": ModuleType("django.contrib"),
            "django.contrib.auth": auth,
            "django.db": database,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.space = {
            "Http404": Http404,
            "COOKIE": "mpw_trx_guest_owner",
            "COOKIE_AGE": 30 * 86400,
            "SALT": "mpw.trx.guest.owner.v1",
            "MAX_COOKIE": 512,
            "secrets": secrets,
            "signing": SimpleNamespace(
                loads=lambda raw, salt, max_age: {"u": 73},
                dumps=lambda data, salt: "x" * 30,
                BadSignature=BadSignature,
                SignatureExpired=SignatureExpired,
            ),
            "_required_checkout_email": lambda request: "buyer@example.org",
            "_rate_limit": lambda request: None,
            "_guest_username": lambda request: "mpwguest_abc",
        }
        exec(self.code, self.space)

    def _guest(self, *, staff=False, superuser=False, username="mpwguest_abc"):
        return SimpleNamespace(
            pk=73, username=username, email="buyer@example.org", is_active=True,
            is_staff=staff, is_superuser=superuser,
            has_usable_password=lambda: False,
        )

    def test_signed_cookie_never_authenticates_staff_or_superuser(self):
        request = SimpleNamespace(COOKIES={"mpw_trx_guest_owner": "x" * 50})
        for user in (self._guest(staff=True), self._guest(superuser=True)):
            with self.subTest(staff=user.is_staff, superuser=user.is_superuser):
                self.principal = user
                self.assertIsNone(self.space["_read_user"](request))

    def test_signed_cookie_still_accepts_password_disabled_nonprivileged_guest(self):
        self.principal = self._guest()
        request = SimpleNamespace(COOKIES={"mpw_trx_guest_owner": "x" * 50})
        self.assertIs(self.space["_read_user"](request), self.principal)

    def test_guest_id_must_have_guest_prefix(self):
        self.principal = self._guest(username="regular_user")
        request = SimpleNamespace(COOKIES={"mpw_trx_guest_owner": "x" * 50})
        self.assertIsNone(self.space["_read_user"](request))

    def test_first_invoice_rejects_privileged_guest_identity_collision(self):
        for user in (self._guest(staff=True), self._guest(superuser=True)):
            with self.subTest(staff=user.is_staff, superuser=user.is_superuser):
                self.principal = user
                with self.assertRaises(Http404):
                    self.space["_new_user"](SimpleNamespace())

    def test_new_guest_cannot_inherit_privileged_user_model_defaults(self):
        created = []

        class UnsafeDefaultsUser:
            USERNAME_FIELD = "username"
            _meta = SimpleNamespace(get_field=lambda name: SimpleNamespace(unique=True))
            objects = SimpleNamespace(filter=lambda **kwargs: SimpleNamespace(first=lambda: None))

            def __init__(self, **kwargs):
                self.username = kwargs["username"]
                self.pk = 73
                self.email = ""
                self.is_active = False
                self.is_staff = True
                self.is_superuser = True

            def set_unusable_password(self):
                self.password_disabled = True

            def has_usable_password(self):
                return not self.password_disabled

            def save(self, **kwargs):
                created.append((self.is_staff, self.is_superuser, kwargs))

        sys.modules["django.contrib.auth"].get_user_model = lambda: UnsafeDefaultsUser
        sys.modules["django.db"].transaction.atomic = nullcontext
        user, token = self.space["_new_user"](SimpleNamespace())
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.password_disabled)
        self.assertEqual(user.email, "buyer@example.org")
        self.assertEqual(len(created), 2)
        self.assertEqual(token, "x" * 30)


if __name__ == "__main__":
    unittest.main()
