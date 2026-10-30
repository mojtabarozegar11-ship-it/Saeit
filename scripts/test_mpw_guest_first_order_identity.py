#!/usr/bin/env python3
"""No-Django, no-database regression for concurrent first TRX guest orders."""
from __future__ import annotations

import ast
import hashlib
import hmac
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
        assert name == "username"
        return Field()


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
        return USERS.get(self.key)


class Manager:
    def filter(self, **kwargs):
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

    def set_unusable_password(self):
        self.unusable = True

    def has_usable_password(self):
        return not self.unusable

    def save(self, force_insert=False):
        assert force_insert is True
        if self.username in USERS:
            raise IntegrityError("duplicate")
        self.pk = len(USERS) + 1
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
        and node.name in ("_guest_username", "_new_user")
    ]
    assert len(functions) == 2
    namespace = {
        "hashlib": hashlib, "hmac": hmac, "secrets": secrets,
        "Http404": Http404, "SALT": "isolated-test", "MAX_COOKIE": 512,
        "_rate_limit": lambda request: None,
        "signing": types.SimpleNamespace(
            dumps=lambda claim, salt: "signed-test:" + str(claim)
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
        META={"CSRF_COOKIE": secret}
    )
    one, _ = functions["_new_user"](request("A" * 32))
    # Force a stale initial lookup to exercise the concurrent insert conflict.
    STALE_LOOKUP = True
    same, _ = functions["_new_user"](request("A" * 32))
    other, _ = functions["_new_user"](request("B" * 32))
    assert one.pk == same.pk and one.pk != other.pk
    assert len(USERS) == 2
    assert not one.has_usable_password()
    assert all(v.username.startswith("mpwguest_") for v in USERS.values())
    try:
        functions["_new_user"](request(""))
    except Http404:
        pass
    else:
        raise AssertionError("missing CSRF session issued a guest")
    print("MPW_GUEST_CONCURRENT_ORDER_IDENTITY=PASS;DATABASE_WRITES=0")


if __name__ == "__main__":
    run()
