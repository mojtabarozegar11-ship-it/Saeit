"""Static and safe-route tests for the seven-page SAMAN release."""
import ast
from pathlib import Path
import unittest

from scripts.saman_patch import patch_views

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "templates" / "saman"
SECTIONS = {
    "learn": ("Learning that moves with you.", "learn-saman"),
    "play": ("More than one way to play.", "play-saman"),
    "products": ("Useful resources, made to keep.", "products-saman"),
    "membership": ("More depth for committed learners.", "membership-saman"),
    "partners": ("Good work grows through collaboration.", "partners-saman"),
    "about": ("A broader home for curiosity.", "about-saman"),
}


class SamanIndependentPages(unittest.TestCase):
    def test_home_is_kept(self):
        home = (S / "index.html").read_text(encoding="utf-8")
        self.assertIn("SAMAN collection", home)
        self.assertIn("Explore MojPlayWin", home)

    def test_six_distinct_complete_english_templates(self):
        seen_titles = set()
        for section, (marker, slug) in SECTIONS.items():
            with self.subTest(section=section):
                source = (S / f"{section}.html").read_text(encoding="utf-8")
                self.assertIn('<html lang="en">', source)
                self.assertIn(f'data-saman-page="{section}"', source)
                self.assertIn(f'aria-current="page"', source)
                self.assertIn(marker, source)
                self.assertIn(f'<link rel="canonical" href="https://mojplaywin.com/saman/{slug}/">', source)
                self.assertIn('<nav class="navlinks"', source)
                self.assertIn('<main id="top"', source)
                self.assertIn('</main>', source)
                self.assertIn('</body>', source)
                self.assertGreater(len(source), 15000)
                self.assertNotIn("{% elif", source)
                self.assertNotIn("{% endif", source)
                title = source.split("<title>", 1)[1].split("</title>", 1)[0]
                self.assertNotIn(title, seen_titles)
                seen_titles.add(title)

    def test_interactive_features(self):
        learn = (S / "learn.html").read_text(encoding="utf-8")
        play = (S / "play.html").read_text(encoding="utf-8")
        shop = (S / "products.html").read_text(encoding="utf-8")
        partners = (S / "partners.html").read_text(encoding="utf-8")
        self.assertIn("check-learning", learn)
        self.assertIn('id="memory-game"', play)
        self.assertIn('id="saman-guess-button"', play)
        self.assertIn("product-filter-status", shop)
        self.assertIn('id="brief-output"', partners)
        self.assertIn("does not submit data", partners)

    def test_legacy_renderer_upgrade_is_safe_and_idempotent(self):
        old = '''
from django.shortcuts import render
from django.views.decorators.cache import never_cache
@never_cache
def saman_section_page(request, section):
    from django.http import Http404
    section_map = {"learn-saman": "learn"}
    if section not in section_map:
        raise Http404
    return render(request, "saman/index.html", {"saman_section": section_map[section]})

def platform_page(request, section):
    pass
'''
        new = patch_views(old)
        ast.parse(new)
        self.assertIn('render(request, "saman/" + section_map[section] + ".html")', new)
        self.assertNotIn('render(request, "saman/index.html",', new)
        self.assertEqual(new, patch_views(new))
        with self.assertRaises(ValueError):
            patch_views(old.replace('return render(request, "saman/index.html", {"saman_section": section_map[section]})', "return 'unexpected'"))


if __name__ == "__main__":
    unittest.main()
