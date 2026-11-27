"""Offline regression for two public MOJ PROP sitemap additions.

Keep the baseline English paths unchanged; test the separately appended guides,
same-origin upstream, and exclusions from both sets. No network, DB or payments.
"""
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
        match = re.search(r"\$mojPropPaths\s*=\s*\[(.*?)\];", cls.source, re.S)
        assert match is not None, "Missing fixed public English sitemap list"
        cls.original_paths = re.findall(r"'(/[^']+)'", match.group(1))
        cls.appended_paths = re.findall(r"\$mojPropPaths\[\]\s*=\s*'(/[^']+)';", cls.source)

    def test_verified_guides_exactly_once_in_appended_urls(self):
        self.assertEqual(tuple(self.appended_paths), GUIDES)
        self.assertEqual(len(set(self.original_paths + self.appended_paths)),
                         len(self.original_paths + self.appended_paths))

    def test_baseline_english_routes_remain_unchanged(self):
        self.assertEqual(len(self.original_paths), 12)
        self.assertEqual(self.original_paths[-1], "/moj-prop/catalog/")

    def test_no_sensitive_routes_in_public_sitemap_urls(self):
        forbidden = ("checkout", "invoice", "admin", "recover", "status",
                     "reconcile", "moj-prop-intake")
        self.assertFalse([p for p in self.original_paths + self.appended_paths
                          if any(k in p for k in forbidden)])

    def test_same_origin_fetch_and_guard_kept(self):
        for marker in (
            "CURLOPT_SSL_VERIFYPEER => true",
            "CURLOPT_FOLLOWLOCATION => false",
            "fallbackSitemap()",
            "array_push($mojPropPaths, ...$mojPropLocalePaths)",
        ):
            self.assertIn(marker, self.source)


if __name__ == "__main__":
    unittest.main()
