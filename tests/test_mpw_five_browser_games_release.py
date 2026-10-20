"""Static release checks: not a substitute for live-device or commercial QA."""
from pathlib import Path
import re
import subprocess
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1] / "site_releases" / "mojplaywin" / "games-20261020"
SLUGS = ("pulse-forge", "beacon-labyrinth", "cipher-garden", "skyline-keeper", "nebula-salvage")

class TestMpwFiveBrowserGames(unittest.TestCase):
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
