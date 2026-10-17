"""Regression guards for shared MojPlayWin main-site presentation only."""
from pathlib import Path

from django.template.loader import get_template
from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "core" / "templates"
BRAND_SHELL = TEMPLATES / "brands" / "mojplaywin" / "base.html"
MAIN_SHELL = TEMPLATES / "mojplaywin" / "theme.html"
UNIFIED = TEMPLATES / "mojplaywin" / "unified_visual_tokens.html"
HOME = TEMPLATES / "mojplaywin" / "home.html"
SECTION = TEMPLATES / "mojplaywin" / "section.html"
STORE = TEMPLATES / "mojplaywin" / "store.html"


class MojPlayWinUnifiedPagesTests(SimpleTestCase):
    def test_only_main_site_template_family_uses_unified_design_tokens(self):
        snippet = '{% include "mojplaywin/unified_visual_tokens.html" %}'
        self.assertEqual(MAIN_SHELL.read_text(encoding="utf-8").count(snippet), 1)
        self.assertNotIn(snippet, BRAND_SHELL.read_text(encoding="utf-8"))
        css = UNIFIED.read_text(encoding="utf-8")
        for required in (
            "--mpw-unified-black", "--mpw-unified-gold",
            ".mw-site-nav{", ".mw-card{",
            ".mw-site-footer{", "prefers-reduced-motion",
            ".mw-page-hero.mw-unified-hero", "mw-unified-crumbs",
        ):
            self.assertIn(required, css)
        self.assertNotIn("body:has(", css)
        self.assertNotIn("mojplaywin-brand-pages", css)
        self.assertNotIn(".mpw-", css)

    def test_main_home_store_and_all_sections_keep_main_menus_and_footers(self):
        for template in (HOME, SECTION, STORE):
            with self.subTest(name=template.name):
                html = template.read_text(encoding="utf-8")
                self.assertIn('{% include "mojplaywin/theme.html" %}', html)
                self.assertIn('{% include "mojplaywin/footer.html" %}', html)

    def test_section_keeps_original_content_and_matches_store_hero_pattern(self):
        section = SECTION.read_text(encoding="utf-8")
        store = STORE.read_text(encoding="utf-8")
        for text in (
            'class="mw-page-hero mw-hero mw-unified-hero"',
            'class="mw-unified-crumbs"',
            'aria-labelledby="mpw-page-title"',
            'id="mpw-discover"',
            '{{ section_title }}', '{{ section_lead }}',
            'section_image', 'for title,text in cards',
            'section_note', 'active_venture',
            'for chapter in page_content.chapters',
            'for item in page_content.faqs',
            'for link in page_content.links',
        ):
            self.assertIn(text, section)
        for text in (
            'class="mw-hero mw-unified-hero"',
            'class="mw-unified-crumbs"',
            'aria-labelledby="mpw-store-title"',
            'for product in products', '{{ product.url }}',
            '{% static product.image %}',
            'href="/market/"', 'href="/knowledge/"',
        ):
            self.assertIn(text, store)

    def test_all_affected_django_templates_parse(self):
        for template_name in (
            "mojplaywin/home.html", "mojplaywin/store.html",
            "mojplaywin/section.html", "mojplaywin/theme.html",
            "mojplaywin/unified_visual_tokens.html",
            "brands/mojplaywin/base.html", "brands/mojplaywin/page.html",
        ):
            with self.subTest(template_name=template_name):
                self.assertIsNotNone(get_template(template_name))

    def test_brand_shell_does_not_replace_old_page_content(self):
        shell = BRAND_SHELL.read_text(encoding="utf-8")
        self.assertNotIn('class="mojplaywin-brand-pages"', shell)
        self.assertNotIn('mojplaywin/unified_visual_tokens.html', shell)
        self.assertNotIn('mojplaywin/founder_signature.html', shell)
        self.assertIn("{% block content %}{% endblock %}", shell)
        self.assertIn('class="mpw-nav"', shell)
        self.assertIn('class="mpw-footer"', shell)
        self.assertIn('href="/games/"', shell)
        self.assertIn('href="/store/"', shell)
