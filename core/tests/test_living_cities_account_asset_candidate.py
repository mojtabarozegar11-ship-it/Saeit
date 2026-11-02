"""Read-only regression checks for the isolated Living Cities account asset candidate."""
from pathlib import Path
import unittest

from scripts import mpw_living_cities_account_asset_candidate as candidate


class LivingCitiesAccountAssetTests(unittest.TestCase):
    def test_known_20_language_html_switches_to_account_without_moving_assets(self):
        html = ('<html data-lc-edition="browser">'
                'LOCAL SAVE · MOJ1 PAYMENTS UNAVAILABLE'
                '<script src="/living-cities/static/living_cities/app.mjs"></script></html>')
        output = candidate.account_html(html)
        self.assertIn('data-lc-edition="account"', output)
        self.assertIn('LOCAL OR ACCOUNT-SAVED PLAY', output)
        self.assertIn('/living-cities/static/living_cities/app.mjs', output)
        self.assertNotIn('MOJ1 PAYMENTS AVAILABLE', output)

    def test_html_unknown_source_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "html_mode"):
            candidate.account_html('<html data-lc-edition="account"></html>')

    def test_rewrites_only_legacy_living_cities_api_paths(self):
        output = candidate.routes(
            '"/living-cities/api/living-cities/world/" and '
            '"/living-cities/api/auth/login/"', "app")
        self.assertIn('/api/living-cities/world/', output)
        self.assertIn('/api/living-cities/auth/login/', output)
        self.assertNotIn('/living-cities/api/', output)

    def test_unrecognized_tycoon_contract_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "global|tycoon"):
            candidate.account_tycoon('fetch("/living-cities/api/living-cities/tycoon/")')

    def test_account_tour_explicitly_labels_local_only_missions(self):
        source = (
            "browserSnapshots(localStorage)\n"
            "weeklyExpedition(world,tycoon,localStorage)\n"
            "' · '+safe(GT(\"worldSafety\",lang))+'</p>';")
        output = candidate.account_global_shell(source)
        self.assertIn("WORLD TOUR PROGRESS IS LOCAL-ONLY, NOT ACCOUNT-SYNCED",
                      output)
        with self.assertRaisesRegex(RuntimeError, "local_world_tour_source_changed"):
            candidate.account_global_shell("' · '+safe(GT(\"worldSafety\",lang))+'</p>';")

    def test_csrf_requires_same_origin_and_login_rotation(self):
        self.assertIn('credentials: "same-origin"', candidate.CSRF_HELPER)
        self.assertIn('cache: "no-store"', candidate.CSRF_HELPER)
        self.assertIn('/api/living-cities/auth/csrf/', candidate.CSRF_HELPER)
        self.assertIn('setCsrfToken', candidate.CSRF_HELPER)

    def test_payment_and_publish_remain_disabled(self):
        self.assertEqual(candidate.STAGE.parent, candidate.ROOT)
        self.assertEqual(candidate.PUBLIC.parent, candidate.SITE)
        self.assertEqual(len(candidate.ASSETS), 16)
        self.assertFalse(hasattr(candidate, "publish"))
        self.assertFalse(hasattr(candidate, "rollback"))
        self.assertNotEqual(candidate.REVIEW_OWNER, candidate.PUBLIC_OWNER)


if __name__ == "__main__":
    unittest.main()
