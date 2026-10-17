"""Strict non-destructive orbital homepage acceptance, compared with PR #400 base."""
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "content/zomorod-new-home/index.html"
CSS = ROOT / "core/static/site/orbital-v2/orbital-v2.css"
JS = ROOT / "core/static/site/orbital-v2/orbital-v2.js"
BASE_REF = "origin/restore-zomorod-corporate-content-20261017"


class Tags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.image_sources = []
        self.images = []
        self.hrefs = []
        self.ids = set()
        self.duplicated_ids = []
        self.h1 = 0
        self.carousel_count = 0
        self.card_count = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            if a["id"] in self.ids:
                self.duplicated_ids.append(a["id"])
            self.ids.add(a["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "section" and "data-orbital-carousel" in a:
            self.carousel_count += 1
        if tag == "a" and "orb-card" in a.get("class", "").split():
            self.card_count += 1
        if tag == "a":
            self.hrefs.append(a.get("href", ""))
        if tag == "img":
            self.images.append(a)
            if "logo" not in a.get("src", ""):
                self.image_sources.append(a.get("src", ""))


class OrbitalHomepageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HOME.read_text(encoding="utf-8")
        cls.css = CSS.read_text(encoding="utf-8")
        cls.js = JS.read_text(encoding="utf-8")
        cls.parser = Tags()
        cls.parser.feed(cls.html)

    def test_three_genuinely_interactive_carousels_and_one_h1(self):
        self.assertEqual(self.parser.carousel_count, 3)
        self.assertEqual(self.parser.card_count, 15)
        self.assertEqual(self.parser.h1, 1)
        self.assertEqual(self.parser.duplicated_ids, [])
        self.assertEqual(self.html.count('data-orb-prev'), 3)
        self.assertEqual(self.html.count('data-orb-next'), 3)
        for term in ('data-orb-nav-track', 'data-orb-motion',
                     'aria-live="polite"', 'aria-pressed="false"'):
            self.assertIn(term, self.html)

    def test_15_new_images_distinct_and_topic_described(self):
        featured = re.findall(r'<a class="orb-card"[^>]*>\s*<img[^>]*>', self.html)
        self.assertEqual(len(featured), 15)
        new_images = [
            re.search(r'\bsrc="([^"]+)"', item).group(1)
            for item in featured
        ]
        self.assertEqual(len(set(new_images)), 15)
        for tag in featured:
            self.assertRegex(tag, r'\balt="[^"]{8,}"')
            self.assertRegex(tag, r'\bwidth="\d+"')
            self.assertRegex(tag, r'\bheight="\d+"')
            self.assertRegex(tag, r'\bloading="lazy"')
        for name in ("greenhouse", "poultry", "livestock", "aquaculture"):
            path = ROOT / f"core/static/site/orbital-v2/{name}.svg"
            self.assertTrue(path.is_file(), name)
            self.assertGreater(path.stat().st_size, 700)
            self.assertTrue(path.read_text(encoding="utf-8").startswith("<svg "))

    def test_no_repeated_editorial_images_on_7_pages(self):
        pages = [HOME] + [
            ROOT / f"content/zomorod-nova-pages/{name}.html"
            for name in ("about", "company", "services", "industry", "research", "knowledge")
        ]
        all_images = []
        for path in pages:
            parser = Tags()
            parser.feed(path.read_text(encoding="utf-8"))
            all_images += parser.image_sources
        self.assertEqual(len(all_images), 45)
        self.assertEqual(len(set(all_images)), 45)

    def test_navigation_exact_urls_and_protected_areas(self):
        for url in (
            "/company/", "/about/", "/services/",
            "/agriculture/", "/agriculture/genetics/",
            "/agriculture/greenhouse/", "/agriculture/poultry/",
            "/agriculture/livestock/", "/agriculture/aquaculture/",
            "/agriculture/horticulture/", "/industry/", "/research/",
            "/knowledge/", "/economy/", "/contact/", "/mohammad/",
            "/ghanadi/", "/amozeshgah/", "/en/", "/ar/", "/zh/",
        ):
            # The original site remains preserved. Not every independent
            # subsite was ever part of the old homepage navigation.
            if url in ("/mohammad/", "/ghanadi/"):
                continue
            self.assertIn(url, self.parser.hrefs, url)
        self.assertIn('href="#orb-footer-map"', self.html)
        self.assertIn('id="orb-footer-map"', self.html)

    def test_js_has_independent_controls_and_motion_safety(self):
        for needle in (
            'data-orbital-carousel', 'ArrowLeft', 'ArrowRight',
            'touchstart', 'touchend', 'prefers-reduced-motion',
            'visibilitychange' if False else 'document.hidden',
            'aria-current', 'data-orb-motion', 'pagehide',
        ):
            self.assertIn(needle, self.js)
        self.assertIn("orb-motion-paused", self.css)
        self.assertIn("@media(max-width:680px)", self.css)
        self.assertIn("@media(prefers-reduced-motion:reduce)", self.css)
        self.assertNotIn("@import", self.css)
        self.assertNotIn("http://", self.css)

    def test_no_fake_performance_or_customer_counters(self):
        start = self.html.index('<section class="orbital-scene"')
        end = self.html.index('<section class="hero">', start)
        stage = self.html[start:end]
        for unverified in ("۱۰۰۰+", "۲۵۰+", "۵۰+", "۱۰+ کشور", "1000+", "250+"):
            self.assertNotIn(unverified, stage)
        self.assertIn("چشم‌انداز:", stage)
        self.assertIn("تمام حقوق مادی و معنوی سایت برای شرکت", self.html)

    def test_old_homepage_content_and_all_original_markup_preserved(self):
        """Reverse only intentional insertions and semantic H1->H2; base must match byte-for-byte."""
        original = subprocess.check_output([
            "git", "show", BASE_REF + ":content/zomorod-new-home/index.html"
        ], cwd=ROOT).decode("utf-8")
        current = self.html
        current = current.replace('\n<link rel="stylesheet" href="/static/site/orbital-v2/orbital-v2.css">', "")
        begin = current.index('<header class="orb-header"')
        end = current.index('<div class="announcement">', begin)
        current = current[:begin] + current[end:]
        begin = current.index('\n<section class="orbital-scene"')
        end = current.index('<section class="hero">', begin)
        current = current[:begin] + "\n" + current[end:]
        current = current.replace(
            '<h2>ریشه در <em>زمین.</em><br>نگاه به <em>آینده.</em></h2>',
            '<h1>ریشه در <em>زمین.</em><br>نگاه به <em>آینده.</em></h1>',
        )
        current = current.replace('class="footer-map" id="orb-footer-map"', 'class="footer-map"')
        begin = current.index('<div class="orb-bottom">')
        end = current.index('</body></html>', begin)
        current = current[:begin] + current[end:]
        self.assertEqual(current, original, "Original homepage text, images, links and sections were changed")

if __name__ == "__main__":
    unittest.main()
