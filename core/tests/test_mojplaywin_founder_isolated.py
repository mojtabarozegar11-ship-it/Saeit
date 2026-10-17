"""Fail-closed source check for the isolated MojPlayWin-only founder footer."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SIGNATURE = ROOT / "core/templates/mojplaywin/founder_signature.html"
FOOTER = ROOT / "core/templates/mojplaywin/footer.html"
LEGACY = ROOT / "core/templates/brands/mojplaywin/base.html"
INCLUDE = '{% include "mojplaywin/founder_signature.html" %}'
COPYRIGHT = "© 2022 MojPlayWin. All rights reserved."


class MojPlayWinFounderFooterIsolationTests(unittest.TestCase):
    def test_signature_is_accessible_and_responsive(self):
        signature = SIGNATURE.read_text(encoding="utf-8")
        for expected in ("Mojtaba Roozegar", "mpw-founder-plaque", "mpw-founder-name",
                         "aria-label=", "@media(max-width:540px)", "@media(forced-colors:active)"):
            self.assertIn(expected, signature)

    def test_new_and_existing_footer_families_both_include_signature(self):
        for path in (FOOTER, LEGACY):
            with self.subTest(path=str(path)):
                html = path.read_text(encoding="utf-8")
                self.assertEqual(html.count(INCLUDE), 1)
                self.assertIn(COPYRIGHT, html)

    def test_original_navigation_remains_present(self):
        footer = FOOTER.read_text(encoding="utf-8")
        legacy = LEGACY.read_text(encoding="utf-8")
        for url in ("/research/", "/knowledge/", "/studio/", "/store/", "/company/",
                    "/contact/", "/privacy/", "/terms/", "/cookies/"):
            self.assertIn('href="' + url + '"', footer)
        for url in ("/store/", "/products/", "/services/", "/games/", "/ai/",
                    "/blockchain/", "/global-business/", "/support/", "/about/", "/contact/"):
            self.assertIn('href="' + url + '"', legacy)


if __name__ == "__main__":
    unittest.main()
