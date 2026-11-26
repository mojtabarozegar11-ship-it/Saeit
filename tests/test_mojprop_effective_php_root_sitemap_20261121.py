"""Contract for the actual cPanel PHP root-sitemap rewrite in English MOJ PROP.

No live network calls, databases, payments, application starts or credentials.
"""
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
LIVE_PHP_MIRROR = ROOT / "ops/cpanel/mojplaywin/sitemap/_mpw_sitemap_three_indexable_20261017.php"
ENGLISH_SITEMAP = ROOT / "templates/moj-prop/sitemap.xml"
BASE = "https://mojprop.top"
BASELINE_MOJ_PROP = {"/moj-prop/", "/moj-prop/starter-30-trx/"}


class MojPropEffectivePHPXmlSitemapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = LIVE_PHP_MIRROR.read_text("utf-8")
        root = ElementTree.fromstring(ENGLISH_SITEMAP.read_text("utf-8"))
        cls.locs = [
            node.text for node in root.findall(
                ".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
            )
        ]

    def test_exactly_fourteen_public_english_canonicals(self):
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

    def test_effective_low_count_php_adds_all_nonbaseline_moj_prop_paths(self):
        match = re.search(
            r"\$mojPropPaths\s*=\s*\[([^\]]+)\];",
            self.source,
        )
        self.assertIsNotNone(match)
        paths = re.findall(r"'(/moj-prop/[^']*)'", match.group(1))
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(len(paths), 12)
        required = {urlsplit(u).path for u in self.locs} - BASELINE_MOJ_PROP
        self.assertEqual(set(paths), required)
        self.assertIn("if ($locCount < 20)", self.source)
        self.assertIn("array_merge($paths, $mojPropPaths)", self.source)
        self.assertIn("X-MPW-Sitemap-Augmentation: moj-prop-only-low-count", self.source)

    def test_passthrough_rewrite_and_original_xml_protection_remain(self):
        for marker in [
            "https://mojplaywin.com/sitemap.xml?__mpw_sitemap_passthru=1",
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
                self.assertIn(marker, self.source)
        self.assertEqual(self.source.count("$mojPropPaths ="), 1)
        self.assertTrue(self.source.startswith("<?php"))
        self.assertTrue(self.source.rstrip().endswith("echo $body;"))


if __name__ == "__main__":
    unittest.main()
