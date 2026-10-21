"""Static release checks: not a substitute for live-device or commercial QA."""
from pathlib import Path
import re
import subprocess
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1] / "site_releases" / "mojplaywin" / "games-20261021"
SLUGS = ("pulse-forge", "beacon-labyrinth", "cipher-garden", "skyline-keeper", "nebula-salvage")

class TestMpwFiveEnhancedBrowserGames(unittest.TestCase):
    def test_five_distinct_no_external_scripts(self):
        self.assertEqual(len(SLUGS), 5)
        self.assertEqual(len(set(SLUGS)), 5)
        sources = []
        for slug in SLUGS:
            with self.subTest(slug=slug):
                s = (ROOT / slug / "index.html").read_text(encoding="utf-8")
                sources.append(s)
                self.assertGreater(len(s), 2500)
                for token in ('<html lang="en">', 'name="viewport"', 'role="status"', 'localStorage', 'not a Google Play release', 'href="/games/"'):
                    self.assertIn(token, s, f"{slug}: {token}")
                for token in ('<script src=', 'fetch(', 'XMLHttpRequest', 'eval(', 'http://'):
                    self.assertNotIn(token, s, f"{slug}: {token}")
                self.assertEqual(len(re.findall(r'<script>(.*?)</script>', s, flags=re.S)), 1)
        self.assertEqual(len(set(sources)), 5)

    def test_live_seo_and_beta_disclosures(self):
        import json
        url = "https://mojplaywin.com/game-releases/20261021/"
        for slug in SLUGS:
            with self.subTest(slug=slug):
                s = (ROOT / slug / "index.html").read_text(encoding="utf-8")
                self.assertIn('<link rel="canonical" href="' + url + slug + '/index.html">', s)
                self.assertIn('content="index,follow', s)
                self.assertIn('<script type="application/ld+json">', s)
                self.assertIn('BETA', s)
                self.assertIn('type="button"', s)
                self.assertIn('id="pauseButton"', s)
                self.assertIn('id="soundButton"', s)
                data = re.search(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)
                self.assertIsNotNone(data)
                payload = json.loads(data.group(1))
                self.assertEqual(payload["url"], url + slug + "/index.html")
                self.assertEqual(payload["offers"]["price"], "0")
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(sitemap.count("<loc>"), 6)

    def test_catalog_links_all_five(self):
        s = (ROOT / "index.html").read_text(encoding="utf-8")
        for slug in SLUGS:
            self.assertIn(f'./{slug}/index.html', s)
        self.assertEqual(s.count('class="card"'), 5)

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_scripts_parse(self):
        for slug in SLUGS:
            s = (ROOT / slug / "index.html").read_text(encoding="utf-8")
            code = re.search(r'<script>(.*?)</script>', s, flags=re.S).group(1)
            proc = subprocess.run(["node", "--check"], input=code, text=True, capture_output=True, timeout=12, check=False)
            self.assertEqual(proc.returncode, 0, f"{slug}: {proc.stderr}")

if __name__ == "__main__": unittest.main()
