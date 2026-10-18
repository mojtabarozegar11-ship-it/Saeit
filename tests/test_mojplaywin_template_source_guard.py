"""Offline isolated-template and shared-deploy safety assertions."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MojPlayWinTemplateSourceGuards(unittest.TestCase):
    def test_main_page_templates_use_only_own_shell(self):
        for filename in ("home.html", "section.html", "store.html"):
            template = (ROOT / "core/templates/mojplaywin" / filename).read_text(encoding="utf-8")
            self.assertIn('{% extends "mojplaywin/site_base.html" %}', template)
            self.assertNotIn('{% extends "base.html" %}', template)
            self.assertNotIn('{% include "mojplaywin/theme.html" %}', template)
            self.assertNotIn('{% include "mojplaywin/footer.html" %}', template)

    def test_legacy_main_brand_shares_shell(self):
        template = (ROOT / "core/templates/brands/mojplaywin/base.html").read_text(encoding="utf-8")
        self.assertIn('{% extends "mojplaywin/site_base.html" %}', template)

    def test_protected_shared_passenger_deploy_remains_off(self):
        source = (ROOT / ".github/workflows/mojplaywin-main-deploy.yml").read_text(encoding="utf-8")
        self.assertIn('if: ${{ false }}', source)

    def test_logo_is_a_real_cacheable_static_asset(self):
        template = (ROOT / "core/templates/mojplaywin/theme.html").read_text(encoding="utf-8")
        self.assertNotIn("data:image/jpeg;base64,", template)
        self.assertIn("site/mojplaywin-header-emblem.jpg", template)
        self.assertTrue((ROOT / "core/static/site/mojplaywin-header-emblem.jpg").exists())

if __name__ == "__main__":
    unittest.main()
