"""Isolated test settings for Moj Prop and commerce integration tests.

This module is for CI/test execution only. It never points at the production
database and deliberately permits Django's default test host without changing
production security settings.

Example:
    DJANGO_SETTINGS_MODULE=config.test_settings \
    python manage.py test core prop_firm
"""
from __future__ import annotations

import os
import tempfile

from .settings import *  # noqa: F401,F403


# Django's test client uses this host unless a test overrides it. Keep this
# allowance confined to this module; production ALLOWED_HOSTS is unchanged.
ALLOWED_HOSTS = list(ALLOWED_HOSTS)
if "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

# Tests exercise view contracts over HTTP without a real TLS terminator.
SECURE_SSL_REDIRECT = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Both database aliases use one isolated SQLite file so router-backed models
# participate in the same test dataset. CI can provide a unique path; the
# default is process-scoped and never uses the production MySQL database.
_TEST_SQLITE = os.environ.get(
    "MOJPROP_TEST_SQLITE_PATH",
    os.path.join(tempfile.gettempdir(), f"mojprop-test-{os.getpid()}.sqlite3"),
)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _TEST_SQLITE,
    },
    "mojprop": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _TEST_SQLITE,
    },
}
