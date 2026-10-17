"""All independent MojPlayWin subsites are immutable during main-site design."""
import unittest

from scripts.mojplaywin_subsite_scope_guard import KNOWN_EXAMPLES, evaluate, permitted


class MojPlayWinSubsiteScopeGuardTests(unittest.TestCase):
    def test_all_current_main_only_files_are_allowed(self):
        permitted_paths = (
            "core/mojplaywin_views.py",
            "core/mojplaywin_web_views.py",
            "core/mojplaywin_atelier_preview_urls.py",
            "core/mojplaywin_editorial.py",
            "core/templates/mojplaywin/home.html",
            "core/templates/mojplaywin/orbital_experience.html",
            "core/templates/brands/mojplaywin/page.html",
            "core/static/site/mojplaywin-atelier/orbits.css",
            "core/static/site/mojplaywin-atelier/official-coin-80.webp",
            "core/static/site/mojplaywin-atelier-v4.css",
            "core/tests/test_mojplaywin_orbital_experience.py",
            "tests/test_mojplaywin_subsite_scope_guard.py",
            "scripts/mojplaywin_product_preservation_snapshot.py",
            ".github/workflows/mojplaywin-site-quality-agent.yml",
            "quality/mojplaywin-acceptance-100.json",
        )
        for path in permitted_paths:
            with self.subTest(path=path):
                self.assertTrue(permitted(path), path)

    def test_every_named_and_unnamed_independent_subsite_is_blocked(self):
        protected_source_paths = (
            "farnaz/urls.py",
            "core/templates/farnaz/home.html",
            "core/templates/mojtaba_roozegar/page.html",
            "core/templates/picm/studio.html",
            "core/templates/studio_roham/home.html",
            "core/templates/saman/main.html",
            "core/templates/zahra_crypto/page.html",
            "core/templates/taniya/home.html",
            "core/templates/future_unknown_child/main.html",
            "subsites/my-new-company/urls.py",
            "new-unknown-child/index.html",
            "core/static/site/other-child-site.css",
            "core/static/site/heroes/legacy-shared.webp",
            "core/migrations/0035_payments.py",
            "core/models.py",
            "core/admin.py",
            "core/commerce_views.py",
            "config/urls.py",
            "config/settings.py",
            "core/templates/base.html",
            "scripts/deploy_mojplaywin_branding.py",
            ".github/workflows/mojplaywin-main-deploy.yml",
            ".htaccess",
            "passenger_wsgi.py",
            "zomorodmelal/special/urls.py",
            "core/templates/brands/zomorod/home.html",
            "quality/other-brand-summary.json",
        )
        for path in protected_source_paths:
            with self.subTest(path=path):
                self.assertFalse(permitted(path), path)
        self.assertIn("/mojtaba.roozegar/", KNOWN_EXAMPLES)
        self.assertIn("/farnaz/", KNOWN_EXAMPLES)
        self.assertIn("/picm/", KNOWN_EXAMPLES)

    def test_no_delete_no_type_change_no_protected_file_even_with_other_passes(self):
        valid = [("M", "core/templates/mojplaywin/home.html")]
        self.assertTrue(evaluate(valid)["source_scope_accepted"])
        for invalid in (
            [("M", "core/templates/mojplaywin/home.html"), ("M", "config/urls.py")],
            [("D", "core/templates/mojplaywin/home.html")],
            [("T", "core/static/site/mojplaywin-atelier/orbits.css")],
            [("A", "core/templates/future-unknown-site/index.html")],
        ):
            with self.subTest(invalid=invalid):
                result = evaluate(invalid)
                self.assertFalse(result["source_scope_accepted"])
                self.assertFalse(result["release_authorized"])

    def test_even_accepted_source_changes_never_authorize_live_deployment(self):
        report = evaluate([("M", "core/templates/mojplaywin/home.html")])
        self.assertTrue(report["source_scope_accepted"])
        self.assertFalse(report["release_authorized"])
        self.assertFalse(report["runtime_isolation_verified"])
        self.assertFalse(report["all_live_subsites_discovered"])
        self.assertFalse(report["live_subsites_preserved_verified"])

    def test_prefix_lookalikes_are_not_allowed(self):
        for name in (
            "core/templates/mojplaywin-other/home.html",
            "core/static/site/mojplaywin-atelier-other.css",
            "scripts/mojplaywin_backup_restart.sh",
            "../config/urls.py",
            "/core/templates/mojplaywin/home.html",
            "core/templates/mojplaywin/../../config/urls.py",
            "core/templates/mojplaywin//bad.html",
        ):
            with self.subTest(name=name):
                self.assertFalse(permitted(name), name)


if __name__ == "__main__":
    unittest.main()
