"""All main MojPlayWin section footers carry the founder name exactly once.

The main-only template include MUST NOT appear in protected child-site renderings
or in the shared and legacy base templates. Read-only HTTP/Django checks.
"""
from pathlib import Path

from django.test import TestCase, override_settings

from core.mojplaywin_views import VENTURES

ROOT = Path(__file__).resolve().parents[2]
FOOTER = ROOT / "core/templates/mojplaywin/footer.html"
BRAND_BASE = ROOT / "core/templates/brands/mojplaywin/base.html"
SHARED_BASE = ROOT / "core/templates/base.html"
SIGNATURE = ROOT / "core/templates/mojplaywin/founder_signature.html"

TOPIC_PATHS = (
    "/agriculture/", "/industry/", "/research/", "/knowledge/",
    "/economy/", "/studio/", "/market/", "/agents/", "/company/",
)
ROOT_PATHS = ("/", "/store/")


@override_settings(ALLOWED_HOSTS=[
    "testserver", "mojplaywin.com", "www.mojplaywin.com",
    "zomorodmelal.ir",
])
class MainMojPlayWinFooterCoverageTests(TestCase):
    def test_main_home_store_nine_topics_eight_ventures_have_exact_name_inside_footer(self):
        paths = ROOT_PATHS + TOPIC_PATHS + tuple(entry["url"] for entry in VENTURES)
        self.assertEqual(len(paths), 19)
        self.assertEqual(len(set(paths)), 19)
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                start = html.index('<footer class="mw-site-footer">')
                finish = html.index("</footer>", start)
                fragment = html[start:finish]
                self.assertIn("Mojtaba Roozegar", fragment)
                self.assertEqual(html.count('class="mpw-founder-name"'), 1)
                self.assertIn("© 2022 MojPlayWin. All rights reserved.", fragment)

    def test_protected_subsites_never_include_main_only_gold_footer(self):
        # Only route handlers in this repository are exercised.
        for path in ("/taniya/", "/farnaz/"):
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST="mojplaywin.com")
                if response.status_code == 200:
                    html = response.content.decode("utf-8")
                    self.assertNotIn('class="mpw-founder-name"', html)
                    self.assertNotIn('id="mpw-founder-plaque-design"', html)

    def test_other_company_host_unchanged(self):
        response = self.client.get("/", HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertNotIn('class="mpw-founder-name"', html)

    def test_only_dedicated_main_footer_references_founder_partial(self):
        footer = FOOTER.read_text(encoding="utf-8")
        inclusion = '{% include "mojplaywin/founder_signature.html" %}'
        self.assertEqual(footer.count(inclusion), 1)
        self.assertLess(footer.index(inclusion), footer.index("</footer>"))
        for protected in (BRAND_BASE, SHARED_BASE):
            self.assertNotIn(inclusion, protected.read_text(encoding="utf-8"))
        founder = SIGNATURE.read_text(encoding="utf-8")
        self.assertIn('class="mpw-founder-name">Mojtaba Roozegar</span>', founder)
        self.assertIn("grid-column:1 / -1", founder)
