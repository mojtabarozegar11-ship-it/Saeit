"""Regression tests for the CloudLinux django-environ fallback (no live host needed)."""
import os
import unittest
from unittest.mock import patch

from config.env_compat import Env


class FallbackEnvironmentTests(unittest.TestCase):
    def test_schema_default_debug_false(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIs(Env(DEBUG=(bool, False))("DEBUG"), False)

    def test_debug_string_false_is_boolean_false(self):
        with patch.dict(os.environ, {"DEBUG": "False"}, clear=True):
            self.assertIs(Env(DEBUG=(bool, False))("DEBUG"), False)

    def test_security_boolean_strings_use_boolean_semantics(self):
        with patch.dict(os.environ, {"SECURE_SSL_REDIRECT": "False"}, clear=True):
            self.assertIs(Env()("SECURE_SSL_REDIRECT", default=False), False)
        with patch.dict(os.environ, {"SECURE_SSL_REDIRECT": "True"}, clear=True):
            self.assertIs(Env()("SECURE_SSL_REDIRECT", default=False), True)

    def test_hsts_seconds_is_integer(self):
        with patch.dict(os.environ, {"SECURE_HSTS_SECONDS": "3600"}, clear=True):
            self.assertEqual(Env()("SECURE_HSTS_SECONDS", default=0), 3600)

    def test_missing_required_value_is_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(KeyError):
                Env()("SECRET_KEY")


if __name__ == "__main__":
    unittest.main()
