"""Reference-fidelity visual implementation, only MojPlayWin main homepage.
All tests are sandbox/offline; they never access production or child sites.
"""
from pathlib import Path
from django.test import SimpleTestCase, override_settings

ROOT = Path(__file__).resolve().parents[2]
HOME = ROOT / "core" / "templates" / "mojplaywin"
STATIC = ROOT / "core" / "static" / "site" / "mojplaywin-atelier"


class MojPlayWinReferenceGoldUITests(SimpleTestCase):
    def test_reference_page_is_real_template_with_local_assets(self):
        home = (HOME / "home.html").read_text(encoding="utf-8")
        orbit = (HOME / "orbital_experience.html").read_text(encoding="utf-8")
        css = (HOME / "reference_gold.css").read_text(encoding="utf-8")
        js = (STATIC / "reference-gold-controls.js").read_text(encoding="utf-8")
        self.assertIn('{% include "mojplaywin/reference_gold.css" %}', home)
        self.assertIn("site/mojplaywin-atelier/reference-gold-controls.js", home)
        self.assertIn("MojPlay<em>Win</em>", orbit)
        self.assertIn("Innovative Digital Solutions for a Smarter World", orbit)
        self.assertIn('class="mpo-proof-strip"', orbit)
        self.assertEqual(orbit.count('class="mpo-satellite '), 4)
        self.assertIn("aria-current", js)
        self.assertIn("scrollTo(", js)
        self.assertIn("prefers-reduced-motion", js)
        self.assertIn("@media(max-width:540px)", css)
        self.assertIn("prefers-reduced-motion:reduce", css)
        self.assertNotIn("http://", css)
        self.assertNotIn("https://", css)

    def test_all_original_sections_and_orbits_remain(self):
        home = (HOME / "home.html").read_text(encoding="utf-8")
        orbit = (HOME / "orbital_experience.html").read_text(encoding="utf-8")
        self.assertEqual(orbit.count('class="mpo-ring"'), 3)
        self.assertEqual(orbit.count('class="mpo-orbit-card"'), 18)
        self.assertEqual(home.count('id="home-guide-'), 10)
        self.assertIn('data-deferred-legacy="true"', home)
        self.assertIn('id="site-directory"', home)
        self.assertIn('{% include "mojplaywin/footer.html" %}', home)
        self.assertIn("© 2022 MojPlayWin.", (HOME / "footer.html").read_text())

    @override_settings(ROOT_URLCONF="core.mojplaywin_atelier_preview_urls", ALLOWED_HOSTS=["mojplaywin.com", "localhost", "testserver"])
    def test_home_render_works_and_preserves_menu_and_canonical(self):
        response = self.client.get("/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn("MojPlay<em>Win</em>", html)
        self.assertIn("mojplaywin-reference-gold-inline", html)
        self.assertIn('aria-label="Primary MojPlayWin navigation"', html)
        self.assertIn('href="https://mojplaywin.com/"', html)
        self.assertIn('href="/blockchain/"', html)
        self.assertEqual(html.count('class="mpo-ring"'), 3)
        self.assertEqual(html.count('class="mpo-orbit-card"'), 18)
        self.assertIn("© 2022 MojPlayWin.", html)

    @override_settings(ROOT_URLCONF="core.mojplaywin_atelier_preview_urls", ALLOWED_HOSTS=["mojplaywin.com", "localhost", "testserver"])
    def test_other_main_sections_unchanged_by_home_reference_style(self):
        response = self.client.get("/services/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertNotIn("mojplaywin-reference-gold-inline", html)
        self.assertNotIn('class="mpo-proof-strip"', html)

    def test_safety_no_protected_site_or_payment_changes(self):
        orbit = (HOME / "orbital_experience.html").read_text(encoding="utf-8")
        for forbidden in ("/mojtaba.roozegar/", "/picm/", "/saman/", "/farnaz/",
                          "/studio.Roham/", "/zahra$$/"):
            self.assertNotIn(f'href="{forbidden}"', orbit)
        for source in (HOME / "reference_gold.css", STATIC / "reference-gold-controls.js"):
            contents = source.read_text(encoding="utf-8")
            for dangerous in ("fetch(", "XMLHttpRequest", "localStorage", "paymentIntent",
                              "checkout", "/admin/"):
                self.assertNotIn(dangerous, contents)

    def test_all_31_new_subject_images_are_original_lightweight_and_valid(self):
        from xml.etree import ElementTree
        from hashlib import sha256
        images = STATIC / "topic-images"
        assets = sorted(images.glob("*.svg"))
        self.assertEqual(len(assets), 31)
        fingerprints = set()
        for asset in assets:
            with self.subTest(asset=asset.name):
                raw = asset.read_bytes()
                self.assertLess(len(raw), 12000)
                root = ElementTree.fromstring(raw)
                self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertTrue(root.find("{http://www.w3.org/2000/svg}title") is not None)
                self.assertNotIn(b"<script", raw.lower())
                self.assertNotIn(b"<image", raw.lower(), "Avoid missing external image dependencies")
                self.assertNotIn(b"http://", raw.replace(b"http://www.w3.org/2000/svg", b""))
                self.assertNotIn(b"https://", raw)
                fingerprints.add(sha256(raw).hexdigest())
        self.assertEqual(len(fingerprints), 31, "No copied SVG illustrations")

    @override_settings(ROOT_URLCONF="core.mojplaywin_atelier_preview_urls",
                       ALLOWED_HOSTS=["mojplaywin.com", "localhost", "testserver"])
    def test_no_repeated_non_logo_images_on_complete_homepage(self):
        from collections import Counter
        from html.parser import HTMLParser

        class ImageCollector(HTMLParser):
            def __init__(self):
                super().__init__()
                self.sources = []
            def handle_starttag(self, tag, attrs):
                if tag == "img":
                    source = dict(attrs).get("src", "")
                    if source:
                        self.sources.append(source.split("?")[0])

        response = self.client.get("/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        parser = ImageCollector()
        parser.feed(response.content.decode("utf-8"))
        self.assertGreaterEqual(len(parser.sources), 48, "Expected all existing sections")
        counts = Counter(p for p in parser.sources if "/official-coin-80." not in p)
        self.assertEqual({p: n for p, n in counts.items() if n > 1}, {},
                         "Every non-logo homepage image should be independent")
        orbit = (HOME / "orbital_experience.html").read_text(encoding="utf-8")
        self.assertEqual(orbit.count('class="mpo-orbit-card"'), 18)
        for topic in ("gold-jewelry-craft.svg", "handwoven-carpet.svg",
                      "fuel-mobility-hub.svg", "hospitality-hotel.svg"):
            self.assertIn(topic, orbit)
