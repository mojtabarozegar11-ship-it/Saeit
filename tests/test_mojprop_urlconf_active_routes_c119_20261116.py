"""Moj Prop URLconf regression tests: parse active routes, never comment text.

All cases use temporary files. No server, database, payment, email or network.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import deploy_mojplaywin_moj_prop_backend as installer

INTAKE = "moj-prop-intake/"
STATUS = "moj-prop-status/"
QUOTE = "moj-prop-quote/<str:token>/"
EXPECTED = {
    INTAKE: "mojprop_intake",
    STATUS: "mojprop_receipt_status",
    QUOTE: "customer_quote",
}


class URLConfRouteSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.target = self.root / "config/urls.py"
        self.target.parent.mkdir()
        p = patch.object(installer, "ROOT", self.root)
        p.start()
        self.addCleanup(p.stop)

    def write(self, source):
        self.target.write_text(source, encoding="utf-8")
        return source

    def test_comments_and_strings_do_not_count_as_active_routes(self):
        self.write(
            'from django.urls import path\n'
            'urlpatterns = []\n'
            '# path("moj-prop-intake/", attacker_view)\n'
            '# path("moj-prop-status/", attacker_view)\n'
            '# path("moj-prop-quote/<str:token>/", attacker_view)\n'
            'HELP_TEXT = "path(\\"moj-prop-intake/\\", hidden_view)"\n'
        )
        installer.patch_urlconf(self.target)
        self.assertEqual(installer._declared_url_routes(self.target.read_text()), EXPECTED)

    def test_existing_correct_routes_are_not_duplicated(self):
        original = self.write(
            'from django.urls import path\n'
            'urlpatterns = [\n'
            '  path("moj-prop-intake/", mojprop_intake),\n'
            '  path("moj-prop-status/", mojprop_receipt_status),\n'
            '  path("moj-prop-quote/<str:token>/", customer_quote),\n'
            ']\n'
        )
        installer.patch_urlconf(self.target)
        self.assertEqual(self.target.read_text(), original)

    def test_unreviewed_route_view_fails_before_writing(self):
        original = self.write(
            'from django.urls import path\n'
            'urlpatterns = [path("moj-prop-intake/", attacker_view)]\n'
        )
        with self.assertRaisesRegex(RuntimeError, "unreviewed view"):
            installer.patch_urlconf(self.target)
        self.assertEqual(self.target.read_text(), original)

    def test_duplicate_active_route_fails_before_writing(self):
        original = self.write(
            'from django.urls import path\n'
            'urlpatterns = [\n'
            '  path("moj-prop-intake/", mojprop_intake),\n'
            '  path("moj-prop-intake/", attacker_view),\n'
            ']\n'
        )
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            installer.patch_urlconf(self.target)
        self.assertEqual(self.target.read_text(), original)

    def test_missing_import_fails_closed(self):
        original = self.write('urlpatterns = []\n')
        with self.assertRaisesRegex(RuntimeError, "does not import path"):
            installer.patch_urlconf(self.target)
        self.assertEqual(self.target.read_text(), original)

    def test_only_currently_missing_route_is_added(self):
        self.write(
            'from django.urls import path\n'
            'urlpatterns = [path("moj-prop-intake/", mojprop_intake)]\n'
        )
        installer.patch_urlconf(self.target)
        routes = installer._declared_url_routes(self.target.read_text())
        self.assertEqual(routes, EXPECTED)
        self.assertEqual(self.target.read_text().count('path("moj-prop-intake/"'), 1)


if __name__ == "__main__":
    unittest.main()
