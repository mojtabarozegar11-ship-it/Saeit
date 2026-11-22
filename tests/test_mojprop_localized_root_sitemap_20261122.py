"""Source-only proof for 21 indexable localized Moj Prop pages in submitted root sitemap.

Never calls the live site, creates traffic, writes files, or sends a sitemap submission.
All localized paths below were independently checked on 2026-11-22: 200,
self-canonical, index/follow; PHP update itself still requires controlled deployment.
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
PHP = ROOT / "ops/cpanel/mojplaywin/sitemap/_mpw_sitemap_three_indexable_20261017.php"
ENGLISH = ROOT / "templates/moj-prop/sitemap.xml"
EXPECTED_LANGUAGES = {
    "/moj-prop/languages/",
    *("/moj-prop/languages/" + lang + "/" for lang in (
        "ar-eg", "ar", "bn", "de", "en", "es", "fr", "hi", "id", "ja",
        "mr", "pcm", "pt", "ru", "sw", "te", "tr", "ur", "vi", "zh"
    ))
}


class MojPropLocalizedRootSitemapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = PHP.read_text(encoding="utf-8")
        english_xml = ElementTree.fromstring(ENGLISH.read_text("utf-8"))
        cls.english = {urlsplit(node.text).path for node in english_xml.findall(
            ".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
        )}
        m = re.search(r"\$mojPropLocalePaths\s*=\s*\[([^\]]+)\];", cls.src)
        if not m:
            raise AssertionError("Required fixed locale array missing")
        cls.locale_matches = re.findall(r"'(/moj-prop/languages/[^']*)'", m.group(1))

    def test_01_exact_21_independently_verified_locale_paths(self):
        self.assertEqual(len(EXPECTED_LANGUAGES), 21)
        self.assertEqual(len(self.locale_matches), 21)
        self.assertEqual(set(self.locale_matches), EXPECTED_LANGUAGES)
        self.assertEqual(len(self.locale_matches), len(set(self.locale_matches)))

    def test_02_preserve_all_english_mojprop_pages(self):
        self.assertEqual(len(self.english), 14)
        self.assertEqual(len(self.english & EXPECTED_LANGUAGES), 0)
        self.assertEqual(len(self.english | EXPECTED_LANGUAGES), 35)
        self.assertIn("/moj-prop/", self.english)
        self.assertIn("/moj-prop/starter-30-trx/", self.english)

    def test_03_locale_append_precedes_lowcount_branch(self):
        self.assertEqual(self.src.count("$mojPropPaths ="), 1)
        a = self.src.index("array_push($mojPropPaths, ...$mojPropLocalePaths);")
        b = self.src.index("if ($locCount < 20)")
        self.assertLess(a, b)
        self.assertIn("foreach ($mojPropPaths as $path)", self.src)
        self.assertIn("array_merge($paths, $mojPropPaths)", self.src)

    def test_04_duplicate_and_count_guards(self):
        self.assertIn("count($mojPropLocalePaths) !== 21", self.src)
        self.assertIn("count(array_unique($mojPropLocalePaths)) !== 21", self.src)
        self.assertIn("if ($seen > 1) fallbackSitemap()", self.src)

    def test_05_preserve_preexisting_live_robot_and_store_urls(self):
        self.assertEqual(self.src.count("$mojPropPaths[] = '/mojtaba.bot.ai/';"), 1)
        for sku in ("72", "225", "879"):
            self.assertEqual(self.src.count("'/store/product/" + sku + "/'"), 1)

    def test_06_no_sensitive_routes_in_locale_array(self):
        for path in EXPECTED_LANGUAGES:
            self.assertTrue(path.startswith("/moj-prop/languages/"))
            self.assertNotIn("?", path)
            self.assertNotIn("#", path)
            for bad in ("checkout", "invoice", "status", "recover", "api",
                        "private", "metrics", "admin", "trx-easy"):
                self.assertNotIn(bad, path)

    def test_07_original_sitemap_passthrough_failclosed(self):
        self.assertIn("https://mojplaywin.com/sitemap.xml?__mpw_sitemap_passthru=1",
                      self.src)
        self.assertIn("CURLOPT_SSL_VERIFYPEER => true", self.src)
        self.assertIn("CURLOPT_FOLLOWLOCATION => false", self.src)
        self.assertIn("substr_count($original, '</urlset>') !== 1", self.src)
        self.assertIn("strpos($original, 'https://zomorodmelal.ir/') !== false",
                      self.src)
        self.assertIn("function fallbackSitemap(): never", self.src)

    @unittest.skipUnless(shutil.which("php"), "PHP CLI unavailable")
    def test_08_php_syntax(self):
        proc = subprocess.run(
            [shutil.which("php"), "-n", "-l"],
            input=self.src, capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
