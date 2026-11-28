"""Contract for standalone MojProp sitemap and the separate MojPlayWin PHP sitemap.

No live network calls, databases, payments, application starts or credentials.
"""
from pathlib import Path
import unittest
from urllib.parse import urlsplit
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
MPW_PHP_MIRROR = ROOT / "ops/cpanel/mojplaywin/sitemap/_mpw_sitemap_three_indexable_20261017.php"
MOJPROP_SITEMAP = ROOT / "templates/moj-prop/sitemap.xml"
MOJPROP_ORIGIN = "https://mojprop.top"
MOJPLAYWIN_ORIGIN = "https://mojplaywin.com"


class MojPropStandaloneSitemapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.php = MPW_PHP_MIRROR.read_text("utf-8")
        root = ElementTree.fromstring(MOJPROP_SITEMAP.read_text("utf-8"))
        cls.locs = [
            node.text for node in root.findall(
                ".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
            )
        ]

    def test_exactly_fourteen_public_english_mojprop_canonicals(self):
        self.assertEqual(len(self.locs), 14)
        self.assertEqual(len(self.locs), len(set(self.locs)))
        for url in self.locs:
            parsed = urlsplit(url)
            self.assertEqual(parsed.scheme, "https")
            self.assertEqual(parsed.netloc, "mojprop.top")
            self.assertTrue(parsed.path.startswith("/moj-prop/"))
            self.assertEqual(parsed.query, "")
            self.assertEqual(parsed.fragment, "")
            self.assertNotIn("checkout", parsed.path)
            self.assertNotIn("status", parsed.path)

    def test_legacy_mojplaywin_php_sitemap_excludes_standalone_mojprop_urls(self):
        self.assertIn(MOJPLAYWIN_ORIGIN + "/sitemap.xml?__mpw_sitemap_passthru=1", self.php)
        self.assertNotIn("$mojPropPaths", self.php)
        self.assertNotIn("$mojPropLocalePaths", self.php)
        self.assertIn("preg_replace(", self.php)
        self.assertIn("$mpwLowCountPaths = ['/mojtaba.bot.ai/'];", self.php)
        self.assertIn("X-MPW-Sitemap-Augmentation: mpw-only-low-count", self.php)
        self.assertNotIn("array_merge($paths, $mojPropPaths)", self.php)

    def test_passthrough_rewrite_and_original_xml_protection_remain(self):
        for marker in [
            "CURLOPT_SSL_VERIFYPEER => true",
            "CURLOPT_SSL_VERIFYHOST => 2",
            "CURLOPT_FOLLOWLOCATION => false",
            "CURLOPT_PROTOCOLS => CURLPROTO_HTTPS",
            "function fallbackSitemap()",
            "substr_count($original, '</urlset>') !== 1",
            "strpos($original, 'https://zomorodmelal.ir/') !== false",
            "'REQUEST_METHOD'",
            "'GET'",
            "'mojplaywin.com'",
            "'www.mojplaywin.com'",
        ]:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.php)
        self.assertEqual(self.php.count("$mpwLowCountPaths ="), 1)
        self.assertTrue(self.php.startswith("<?php"))
        self.assertTrue(self.php.rstrip().endswith("echo $body;"))


if __name__ == "__main__":
    unittest.main()
