"""Offline regression for the two final public MOJ PROP sitemap additions."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ops/cpanel/mojplaywin/sitemap/_mpw_sitemap_three_indexable_20261017.php"
GUIDES = (
    "/moj-prop/education/prop-firm-simulated-trading-challenge/",
    "/moj-prop/signals/gold-q4-2026/",
)

class MojPropSitemapGuidesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.path_array = re.search(r"\\$mojPropPaths\\s*=\\s*\\[(.*?)\\];", cls.source, re.S)
        assert cls.path_array is not None

    def test_exact_public_guides_once(self):
        for path in GUIDES:
            self.assertEqual(self.path_array.group(1).count("'" + path + "'"), 1)

    def test_no_sensitive_paths_in_public_prop_paths(self):
        entries = re.findall(r"'(/[^']+)'", self.path_array.group(1))
        forbidden = ("checkout", "invoice", "admin", "recover", "status", "reconcile")
        self.assertFalse([p for p in entries if any(k in p for k in forbidden)])

    def test_same_origin_fetch_and_guard_kept(self):
        self.assertIn("CURLOPT_SSL_VERIFYPEER => true", self.source)
        self.assertIn("CURLOPT_FOLLOWLOCATION => false", self.source)
        self.assertIn("fallbackSitemap()", self.source)
        self.assertIn("array_push($mojPropPaths, ...$mojPropLocalePaths)", self.source)

if __name__ == "__main__":
    unittest.main()
