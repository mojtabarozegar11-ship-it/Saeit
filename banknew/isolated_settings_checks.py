"""Pure configuration regression checks; no database or customer credentials."""
import importlib
import os
import sys
import unittest
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured

CONFIG = "banknew.isolated_settings"
GOOD = {
    "BANKNEW_DJANGO_SECRET_KEY": "Unique-Production-Settings-Fake-Key-For-CI-Only--Do-Not-Deploy-0123456789",
    "BANKNEW_DB_NAME": "isolated_test_db",
    "BANKNEW_DB_USER": "isolated_test_user",
    "BANKNEW_DB_PASSWORD": "non-secret-test-credential",
}


def _fresh_settings():
    sys.modules.pop(CONFIG, None)
    return importlib.import_module(CONFIG)


class IsolatedSettingsChecks(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop(CONFIG, None)

    def test_secrets_mandatory_and_no_weak_defaults(self):
        for missing in GOOD:
            env = dict(GOOD)
            env[missing] = ""
            with self.subTest(missing=missing), patch.dict(os.environ, env):
                with self.assertRaises(ImproperlyConfigured):
                    _fresh_settings()

    def test_private_database_and_secure_cookie_scope(self):
        with patch.dict(os.environ, GOOD):
            s = _fresh_settings()
        self.assertFalse(s.DEBUG)
        self.assertEqual(s.ALLOWED_HOSTS, ["mojplaywin.com"])
        self.assertEqual(s.DATABASES["default"]["ENGINE"], "django.db.backends.mysql")
        self.assertEqual(s.DATABASES["default"]["NAME"], GOOD["BANKNEW_DB_NAME"])
        self.assertEqual(s.ROOT_URLCONF, "banknew.isolated_urls")
        self.assertEqual(s.SESSION_COOKIE_PATH, "/banknew-api/")
        self.assertEqual(s.CSRF_COOKIE_PATH, "/banknew-api/")
        self.assertTrue(s.SESSION_COOKIE_SECURE)
        self.assertTrue(s.CSRF_COOKIE_SECURE)
        self.assertTrue(s.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(s.CSRF_COOKIE_HTTPONLY)
        self.assertTrue(s.SECURE_SSL_REDIRECT)
        self.assertEqual(s.CSRF_TRUSTED_ORIGINS, ["https://mojplaywin.com"])
        self.assertNotIn("core", s.INSTALLED_APPS)
        self.assertNotIn("config", s.ROOT_URLCONF)
        self.assertFalse(any("admin" in app for app in s.INSTALLED_APPS))


if __name__ == "__main__":
    unittest.main()
