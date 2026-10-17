"""Approved black-and-gold orbital design acceptance; source + rendered semantics.

No runtime activation, no real orders/payments, no modification of other sites.
"""
from pathlib import Path
import re

from django.test import TestCase, override_settings

ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / "core" / "templates" / "mojplaywin"
STATIC = ROOT / "core" / "static" / "site" / "mojplaywin-atelier"


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinOrbitalExperienceTests(TestCase):
    def test_three_distinct_interactive_orbits_and_eighteen_real_navigation_cards(self):
        markup = (PAGES / "orbital_experience.html").read_text(encoding="utf-8")
        self.assertEqual(markup.count('class="mpo-ring"'), 3)
        self.assertEqual(markup.count('class="mpo-orbit-card"'), 18)
        self.assertEqual(markup.count('class="mpo-orbit-track"'), 3)
        for ring in ("web", "digital", "ventures"):
            self.assertIn(f'data-orbit="{ring}"', markup)
            self.assertIn(f'id="mpo-ring-{ring}"', markup)
            self.assertIn(f'aria-labelledby="mpo-ring-{ring}"', markup)
        self.assertEqual(markup.count('data-orbit-prev'), 3)
        self.assertEqual(markup.count('data-orbit-next'), 3)
        self.assertIn('data-orbit-toggle', markup)
        self.assertIn('aria-pressed="false"', markup)
        hrefs = re.findall(r'class="mpo-orbit-card" href="([^"]+)"', markup)
        self.assertEqual(len(hrefs), 18)
        self.assertTrue(all(href.startswith("/") for href in hrefs))
        for excluded in ("/mojtaba.roozegar/", "/picm/", "/saman/", "/zahra$$/"):
            self.assertNotIn(excluded, hrefs)

    def test_full_previous_home_content_and_footer_are_preserved(self):
        home = (PAGES / "home.html").read_text(encoding="utf-8")
        self.assertIn('{% include "mojplaywin/orbital_experience.html" %}', home)
        self.assertIn('id="mpw-home-ten-guides"', home)
        self.assertEqual(home.count('id="home-guide-'), 10)
        self.assertIn('id="site-directory"', home)
        self.assertIn("Ideas become knowledge", home)
        self.assertIn('{% for item in features %}', home)
        self.assertIn('{% for item in ventures %}', home)
        self.assertIn('{% include "mojplaywin/footer.html" %}', home)
        self.assertIn("orbits.js", home)
        self.assertIn("orbits.css", home)

    def test_all_media_and_orbital_assets_exist_locally(self):
        markup = (PAGES / "orbital_experience.html").read_text(encoding="utf-8")
        refs = re.findall(r"{%\s*static\s+'([^']+)'\s*%}", markup)
        self.assertGreaterEqual(len(refs), 20)
        for relative in refs:
            with self.subTest(asset=relative):
                self.assertTrue((ROOT / "core" / "static" / relative).is_file())
        for path in ("orbits.css", "orbits.js", "global-technology-orbit.svg"):
            self.assertTrue((STATIC / path).is_file())

    def test_mobile_keyboard_accessibility_and_reduced_motion_are_mandatory(self):
        css = (STATIC / "orbits.css").read_text(encoding="utf-8")
        js = (STATIC / "orbits.js").read_text(encoding="utf-8")
        template = (PAGES / "orbital_experience.html").read_text(encoding="utf-8")
        for required in ("prefers-reduced-motion:reduce", "max-width:540px",
                         "scroll-snap-type:x mandatory", ":focus-visible"):
            self.assertIn(required, css)
        for required in ('event.key === "ArrowRight"', 'event.key === "ArrowLeft"',
                         'pointerdown', 'pointermove', 'scrollBy', 'scrollTo',
                         "reduceMotion.matches", 'document.hidden',
                         'aria-pressed'):
            self.assertIn(required, js)
        self.assertIn('tabindex="0"', template)
        self.assertIn('type="button"', template)

    def test_all_orbit_card_destinations_are_real_renderable_main_site_pages(self):
        from django.urls import resolve

        markup = (PAGES / "orbital_experience.html").read_text(encoding="utf-8")
        urls = sorted(set(re.findall(r'class="mpo-orbit-card" href="([^"]+)"', markup)))
        self.assertGreaterEqual(len(urls), 10)
        for url in urls:
            with self.subTest(url=url):
                resolved = resolve(url)
                self.assertIsNotNone(resolved.func)
                response = self.client.get(url, HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200, f"Broken orbital link: {url}")
                self.assertGreater(len(response.content), 200)

    def test_rendered_home_has_only_one_h1_and_three_real_orbits(self):
        response = self.client.get("/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertEqual(len(re.findall(r"<h1\b", html)), 1)
        self.assertIn("Website engineering that", html)
        self.assertEqual(html.count('class="mpo-ring"'), 3)
        self.assertEqual(html.count('class="mpo-orbit-card"'), 18)
        self.assertIn("© 2022 MojPlayWin", html)
