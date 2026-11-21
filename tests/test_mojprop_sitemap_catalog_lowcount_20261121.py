"""MojPlayWin PHP low-count sitemap and independently verified canonical parity.

Source-only contract; never changes the live PHP handler or .htaccess.
"""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

PHP = (Path(__file__).resolve().parents[1] /
       "ops/cpanel/mojplaywin/sitemap/_mpw_sitemap_three_indexable_20261017.php")
# Preserve the original four route positions while deriving the complete
# English-only list from the independently published canonical XML sitemap.
# This avoids freezing a pre-publication five-page expectation in CI.
ORIGINAL_PREFIX=(
    "/moj-prop/rules/",
    "/moj-prop/signals/",
    "/moj-prop/payment/",
    "/moj-prop/contact/",
)
ENGLISH_XML=(Path(__file__).resolve().parents[1] / "templates/moj-prop/sitemap.xml")
DJANGO_BASE={"/moj-prop/", "/moj-prop/starter-30-trx/"}

class CatalogSitemapSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=PHP.read_text(encoding="utf-8")

    def test_fixed_catalog_present_exactly_once_in_explicit_low_count_paths(self):
        matches=re.findall(r"\$mojPropPaths\s*=\s*\[([^]]+)\];",self.src)
        self.assertEqual(len(matches),1)
        paths=re.findall(r"'(/[^']+/)'",matches[0])
        self.assertEqual(len(paths),len(set(paths)))
        self.assertEqual(tuple(paths[:4]), ORIGINAL_PREFIX)
        self.assertEqual(paths[-1], "/moj-prop/catalog/")
        from urllib.parse import urlsplit
        from xml.etree import ElementTree
        xml=ElementTree.fromstring(ENGLISH_XML.read_text("utf-8"))
        locs=[node.text for node in xml.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
        self.assertEqual(len(locs),14)
        self.assertEqual(len(locs),len(set(locs)))
        expected={urlsplit(url).path for url in locs}-DJANGO_BASE
        self.assertEqual(set(paths),expected)

    def test_fallback_and_separation_remain_present(self):
        for phrase in (
            "REQUEST_METHOD",
            "'GET'",
            "'mojplaywin.com'",
            "'www.mojplaywin.com'",
            "function fallbackSitemap()",
            "https://mojplaywin.com/sitemap.xml?__mpw_sitemap_passthru=1",
            "if ($locCount < 20)",
            "moj-prop-only-low-count",
            "count(array_unique($existingLocs))",
            "foreach ($mojPropPaths as $path)",
            "if ($seen > 1) fallbackSitemap()",
            "$paths = array_merge($paths, $mojPropPaths)",
        ):
            with self.subTest(phrase=phrase):self.assertIn(phrase,self.src)

    def test_no_sensitive_evergreen_or_checkout_routes_in_fixed_list(self):
        block=re.search(r"\$mojPropPaths\s*=\s*\[([^]]+)\];",self.src).group(1)
        for forbidden in ("checkout","invoice","admin","status","recover","samples","api","moj-prop-intake"):
            self.assertNotIn(forbidden,block)

    @unittest.skipUnless(shutil.which("php"),"PHP executable unavailable")
    def test_php_syntax(self):
        proc=subprocess.run([shutil.which("php"),"-n","-l"],
            input=self.src,text=True,capture_output=True,timeout=15)
        self.assertEqual(proc.returncode,0,proc.stdout+" "+proc.stderr)

if __name__=="__main__":unittest.main()
