"""No-delete, content-completeness, SEO and Django admin safety gates.

Applies only to MojPlayWin brand-owned presentation code. No production writes.
"""
from pathlib import Path
from django.contrib import admin
from django.test import TestCase, override_settings

from core.models import Agent, AgentCapability, AgentTask
from core.mojplaywin_editorial import EDITORIAL, editorial_for
from core.mojplaywin_views import SECTIONS, VENTURES

ROOT = Path(__file__).resolve().parents[2]
HEROES = ROOT / "core" / "static"


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinCompletePageGuardTests(TestCase):
    def test_all_existing_specialty_pages_have_original_nonempty_content(self):
        expected = {f"section:{code}" for code in SECTIONS}
        expected |= {f"venture:{venture['slug']}" for venture in VENTURES}
        self.assertEqual(set(EDITORIAL), expected)
        for key, detail in EDITORIAL.items():
            with self.subTest(page=key):
                self.assertGreater(len(" ".join(detail["overview"]).split()), 65)
                self.assertEqual(len(detail["steps"]), 4)
                self.assertEqual(len(detail["deliverables"]), 3)
                self.assertEqual(len(detail["images"]), 3)
                self.assertEqual(len(set(im["path"] for im in detail["images"])), 3)
                self.assertTrue(detail["headline"].strip())
                self.assertTrue(detail["note"].strip())
                self.assertTrue(detail["link"].startswith("/"))
                for item in detail["steps"]:
                    self.assertGreater(len(item["detail"].split()), 12)
                for image in detail["images"]:
                    self.assertTrue((HEROES / image["path"]).is_file(), image["path"])
                    self.assertTrue(image["alt"].strip())
                    self.assertTrue(image["caption"].strip())

    def test_rendered_page_has_unique_editorial_gallery_and_original_content(self):
        cases = [
            ("/research/", "Scientific Research & Innovation", "Questions, evidence"),
            ("/agents/", "AI & Modern Technology", "Design AI agents"),
            ("/ventures/fuel-station/", "Fuel & Mobility", "Fuel and mobility"),
            ("/ventures/cafe-restaurant/", "Cafes & Restaurants", "Restaurant and cafe"),
        ]
        for path, old_title, field_title in cases:
            with self.subTest(path=path):
                r = self.client.get(path, HTTP_HOST="mojplaywin.com")
                self.assertEqual(r.status_code, 200)
                html = r.content.decode("utf-8")
                self.assertIn(old_title, html)
                self.assertIn(field_title, html)
                self.assertIn('data-editorial="mojplaywin-original"', html)
                self.assertEqual(html.count('class="mpx-editorial-figure"'), 3)
                self.assertIn('href="https://mojplaywin.com' + path + '"', html)
                self.assertNotIn('href="https://zomorodmelal.ir' + path + '"', html)

    def test_independent_mojplaywin_base_has_correct_seo_and_no_shared_base(self):
        pages = ROOT / "core" / "templates" / "mojplaywin"
        own_base = (pages / "base.html").read_text(encoding="utf-8")
        self.assertIn('rel="canonical" href="https://mojplaywin.com{{ request.path }}"', own_base)
        self.assertIn("og:site_name", own_base)
        self.assertNotIn("zomorodmelal.ir", own_base)
        for filename in ("home.html", "section.html", "store.html"):
            self.assertIn('{% extends "mojplaywin/base.html" %}',
                          (pages / filename).read_text(encoding="utf-8"))

    def test_django_admin_and_agent_models_are_not_removed(self):
        for model in (Agent, AgentCapability, AgentTask):
            self.assertIn(model, admin.site._registry)
        response = self.client.get("/admin/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_agent_detail_is_educational_not_false_live_status(self):
        content = editorial_for("section", "agents")
        self.assertIsNotNone(content)
        self.assertIn("does not state that any specific", content["note"])
        self.assertIn("Domain ownership", " ".join(content["overview"]))
