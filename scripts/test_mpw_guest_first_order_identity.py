#!/usr/bin/env python3
"""No-Django, no-database regression for concurrent first TRX guest orders."""
from __future__ import annotations

import ast
import hashlib
import hmac
import re
import secrets
import sys
import types
from pathlib import Path


class Http404(Exception):
    pass


class IntegrityError(Exception):
    pass


class Atomic:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Field:
    unique = True


class Meta:
    def get_field(self, name):
        assert name in ("username", "email")
        return types.SimpleNamespace(unique=name == "username", concrete=True,
                                     is_relation=False)


USERS = {}
STALE_LOOKUP = False


class Query:
    def __init__(self, key):
        self.key = key

    def first(self):
        global STALE_LOOKUP
        if STALE_LOOKUP:
            STALE_LOOKUP = False
            return None
        if isinstance(self.key, tuple) and self.key[0] == "pk":
            return next((u for u in USERS.values() if u.pk == self.key[1] and u.is_active), None)
        return USERS.get(self.key)


class Manager:
    def filter(self, **kwargs):
        if "pk" in kwargs:
            return Query(("pk", kwargs["pk"]))
        return Query(next(iter(kwargs.values())))


class User:
    USERNAME_FIELD = "username"
    _meta = Meta()
    objects = Manager()

    def __init__(self, **kwargs):
        self.username = kwargs["username"]
        self.is_active = True
        self.pk = None
        self.unusable = False
        self.email = ""
        # Deliberately unsafe model defaults test explicit guest downgrade.
        self.is_staff = True
        self.is_superuser = True

    def set_unusable_password(self):
        self.unusable = True

    def has_usable_password(self):
        return not self.unusable

    def save(self, force_insert=False, update_fields=None):
        if force_insert:
            if self.username in USERS:
                raise IntegrityError("duplicate")
            self.pk = len(USERS) + 1
            USERS[self.username] = self
            return
        assert self.username in USERS
        USERS[self.username] = self


def install_fake_django():
    for name in ("django", "django.conf", "django.contrib",
                 "django.contrib.auth", "django.db"):
        sys.modules[name] = types.ModuleType(name)
    sys.modules["django.conf"].settings = types.SimpleNamespace(
        SECRET_KEY="regression-test-only"
    )
    sys.modules["django.contrib.auth"].get_user_model = lambda: User
    sys.modules["django.db"].IntegrityError = IntegrityError
    sys.modules["django.db"].transaction = types.SimpleNamespace(atomic=Atomic)


def load_real_functions():
    source = (Path(__file__).resolve().parents[1] /
              "services/mpw_trx_guest_commerce.py").read_text("utf8")
    tree = ast.parse(source)
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in ("_guest_username", "_new_user", "_read_user")
    ]
    assert len(functions) == 3
    namespace = {
        "hashlib": hashlib, "hmac": hmac, "re": re, "secrets": secrets,
        "Http404": Http404, "SALT": "isolated-test", "MAX_COOKIE": 512,
        "COOKIE": "mpw_trx_guest_owner", "COOKIE_AGE": 30 * 86400,
        "_rate_limit": lambda request: None,
        "signing": types.SimpleNamespace(
            dumps=lambda claim, salt: "signed-test:" + str(claim),
            loads=lambda raw, salt, max_age: {"u": 1},
            BadSignature=ValueError, SignatureExpired=ValueError,
        ),
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]),
                 "<isolated-guest-functions>", "exec"), namespace)
    return namespace


def run():
    global STALE_LOOKUP
    install_fake_django()
    functions = load_real_functions()
    request = lambda secret: types.SimpleNamespace(
        META={"CSRF_COOKIE": secret},
        POST={},
    )
    one, _ = functions["_new_user"](request("A" * 32))
    # Force a stale initial lookup to exercise the concurrent insert conflict.
    STALE_LOOKUP = True
    same, _ = functions["_new_user"](request("A" * 32))
    other, _ = functions["_new_user"](request("B" * 32))
    assert one.pk == same.pk and one.pk != other.pk
    assert len(USERS) == 2
    assert all(u.email == u.username + "@guest.mojplaywin.invalid"
               for u in USERS.values())
    # A malicious/legacy posted email is never used as the internal principal.
    injected = types.SimpleNamespace(META={"CSRF_COOKIE": "C" * 32},
                                     POST={"email": "buyer@external.example"})
    fake, _ = functions["_new_user"](injected)
    assert fake.email.endswith("@guest.mojplaywin.invalid")
    assert fake.email != injected.POST["email"]
    assert not one.has_usable_password()
    assert all(v.username.startswith("mpwguest_") for v in USERS.values())
    assert all(not v.is_staff and not v.is_superuser for v in USERS.values())
    # Neither a retained guest cookie nor concurrent re-use may claim staff privileges.
    cookie_req = types.SimpleNamespace(COOKIES={"mpw_trx_guest_owner": "a" * 32})
    assert functions["_read_user"](cookie_req) is one
    one.is_staff = True
    assert functions["_read_user"](cookie_req) is None
    try:
        functions["_new_user"](request("A" * 32))
    except Http404:
        pass
    else:
        raise AssertionError("privileged staff collision accepted")
    one.is_staff = False
    one.is_superuser = True
    assert functions["_read_user"](cookie_req) is None
    try:
        functions["_new_user"](request("A" * 32))
    except Http404:
        pass
    else:
        raise AssertionError("privileged superuser collision accepted")
    one.is_superuser = False
    assert functions["_read_user"](cookie_req) is one
    # Reusing a legacy/altered identity must fail closed, not rewrite data.
    original_email = one.email
    one.email = ""
    try:
        functions["_new_user"](request("A" * 32))
    except Http404:
        pass
    else:
        raise AssertionError("Empty legacy identity silently accepted")
    one.email = original_email
    try:
        functions["_new_user"](request(""))
    except Http404:
        pass
    else:
        raise AssertionError("missing CSRF session issued a guest")
    print("MPW_GUEST_CONCURRENT_ORDER_IDENTITY=PASS;DATABASE_WRITES=0")


if __name__ == "__main__":
    run()
