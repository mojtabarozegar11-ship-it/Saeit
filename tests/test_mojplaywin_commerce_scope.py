"""Negative tests for the main-only MojPlayWin design / commerce scope guard."""
import unittest

from scripts.mojplaywin_commerce_scope import is_allowed_path, check_entries


class MojPlayWinCommerceScopeTests(unittest.TestCase):
    def test_allow_intended_editorial_and_style_files(self):
        for name in (
            "core/mojplaywin_views.py",
            "core/templates/mojplaywin/home.html",
            "core/templates/mojplaywin/store.html",
            "core/static/site/mojplaywin-atelier/topic-images/venture-jewelry.svg",
            "core/tests/test_mojplaywin_unified_pages.py",
            "scripts/mojplaywin_commerce_scope.py",
            "tests/test_mojplaywin_commerce_scope.py",
            ".github/workflows/mojplaywin-commerce-scope-only.yml",
        ):
            with self.subTest(path=name):
                self.assertTrue(is_allowed_path(name))

    def test_block_sensitive_paths_and_all_children(self):
        for name in (
            "core/models.py", "core/commerce_views.py", "core/urls.py",
            "config/urls.py", "core/templates/core/store.html",
            "core/migrations/0001_initial.py",
            "core/payment_views.py", "core/checkout.py", "core/wallet_eth.py",
            "core/templates/mojplaywin/checkout.html",
            "core/templates/mojplaywin/payment.html",
            "core/templates/mojplaywin/product_model.html",
            "core/tests/test_mojplaywin_wallet.py",
            "core/static/site/mojplaywin-atelier/topic-images/venture-wallet.svg",
            "farnaz/views.py", "core/templates/farnaz/base.html",
            "core/templates/mojtaba_roozegar/home.html",
            "core/templates/brands/zomorod/base.html", "core/templates/brands/mojplaywin/base.html", "passenger_wsgi.py",
            "scripts/deploy_mojplaywin_branding.py", "core/templates/base.html",
            "/etc/passwd", "../config/urls.py", "core\\models.py",
        ):
            with self.subTest(path=name):
                self.assertFalse(is_allowed_path(name))

    def test_reject_deletions_renames_and_unknown_scope(self):
        self.assertTrue(check_entries([]))
        self.assertTrue(check_entries([("D", "core/templates/mojplaywin/store.html")]))
        self.assertTrue(check_entries([("T", "core/templates/mojplaywin/theme.html")]))
        self.assertTrue(check_entries([("A", "core/models.py")]))
        self.assertTrue(check_entries([("M", "config/urls.py")]))
        self.assertFalse(check_entries([
            ("A", "core/static/site/mojplaywin-atelier/topic-images/venture-agri.svg"),
            ("M", "core/templates/mojplaywin/store.html"),
        ]))


if __name__ == "__main__":
    unittest.main()
