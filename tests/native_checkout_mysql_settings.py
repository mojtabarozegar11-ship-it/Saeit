"""Ephemeral MySQL CI only — never load or connect to cPanel or VPS.

No production credentials or production hostnames. Test DB is destroyed
with its disposable GitHub Actions container after each workflow run.
"""
import os

from tests.native_checkout_settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "mpw_ci",
        "USER": "root",
        "PASSWORD": os.environ["MPW_TEST_DB_PASSWORD"],
        "HOST": "127.0.0.1",
        "PORT": "3306",
        "OPTIONS": {"charset": "utf8mb4"},
        "TEST": {"NAME": "test_mpw_ci"},
    }
}
