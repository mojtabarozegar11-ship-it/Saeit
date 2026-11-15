"""Release blocker: signed Moj Prop receipts must ship with the intake backend.

All checks are local and synthetic: never contacts cPanel or modifies production.
"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.deploy_mojplaywin_moj_prop_backend import (
    ALL_FILES, REPLACE_FILES, patch_urlconf, selftest,
)


class MojPropReceiptBackendReleaseTests(unittest.TestCase):
    def make_urlconf(self, text):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        target = Path(temp.name) / "urls.py"
        target.write_text(text, encoding="utf-8")
        return target

    def patch(self, target):
        with contextlib.redirect_stdout(io.StringIO()):
            patch_urlconf(target)
        return target.read_text(encoding="utf-8")

    def test_signer_is_both_installed_and_backed_up_for_rollback(self):
        signer = Path("core/mojprop_receipts.py")
        self.assertIn(signer, ALL_FILES)
        self.assertIn(signer, REPLACE_FILES)
        self.assertEqual(ALL_FILES.count(signer), 1)
        self.assertEqual(REPLACE_FILES.count(signer), 1)

    def test_real_repo_backend_selftest_requires_signed_receipt_contract(self):
        root = Path(__file__).resolve().parents[1]
        with contextlib.redirect_stdout(io.StringIO()):
            selftest(root)
        view = (root / "core/mojprop_views.py").read_text(encoding="utf-8")
        self.assertIn("from .mojprop_receipts import", view)
        self.assertIn("def mojprop_receipt_status(", view)

    def test_fresh_urlconf_adds_intake_and_signed_status_once(self):
        url = self.make_urlconf("from django.urls import path\nurlpatterns = []\n")
        after = self.patch(url)
        self.assertEqual(after.count('path("moj-prop-intake/"'), 1)
        self.assertEqual(after.count('path("moj-prop-status/"'), 1)
        self.assertIn("from core.mojprop_views import mojprop_intake, mojprop_receipt_status", after)
        self.assertEqual(self.patch(url), after)

    def test_partial_previous_release_repairs_status_without_duplicate_intake(self):
        initial = (
            "from django.urls import path\nurlpatterns = []\n"
            "from core.mojprop_views import mojprop_intake\n"
            'urlpatterns += [path("moj-prop-intake/", mojprop_intake, name="mojprop_intake")]\n'
        )
        url = self.make_urlconf(initial)
        result = self.patch(url)
        self.assertEqual(result.count('path("moj-prop-intake/"'), 1)
        self.assertEqual(result.count('path("moj-prop-status/"'), 1)
        self.assertIn("from core.mojprop_views import mojprop_receipt_status", result)
        self.assertEqual(result, self.patch(url))

    def test_prior_complete_install_remains_byte_for_byte_unchanged(self):
        original = (
            "from django.urls import path\nurlpatterns = []\n"
            'urlpatterns += [path("moj-prop-intake/", intake)]\n'
            'urlpatterns += [path("moj-prop-status/", receipt)]\n'
        )
        url = self.make_urlconf(original)
        self.assertEqual(self.patch(url), original)

    def test_invalid_urlconf_never_gets_partially_modified(self):
        for content in ("urlpatterns = []\n", "from django.urls import include\nurlpatterns=[]\n"):
            with self.subTest(source=content):
                url = self.make_urlconf(content)
                with self.assertRaises(RuntimeError):
                    self.patch(url)
                self.assertEqual(url.read_text(encoding="utf-8"), content)


if __name__ == "__main__":
    unittest.main()
