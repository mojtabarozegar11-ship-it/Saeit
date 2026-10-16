"""No-delete, content-completeness, SEO and Django admin safety gates.

Applies only to MojPlayWin brand-owned presentation code. No production writes.
"""
from pathlib import Path
from html import unescape
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
                self.assertGreaterEqual(len(" ".join(detail["overview"]).split()), 55)
                self.assertGreaterEqual(len((" ".join(detail["overview"]) + " ".join(step["detail"] for step in detail["steps"]) + " ".join(detail["deliverables"])).split()), 120)
                self.assertEqual(len(detail["steps"]), 4)
                self.assertEqual(len(detail["deliverables"]), 3)
                self.assertEqual(len(detail["images"]), 3)
                self.assertEqual(len(set(im["path"] for im in detail["images"])), 3)
                self.assertTrue(detail["headline"].strip())
                self.assertTrue(detail["note"].strip())
                self.assertTrue(detail["link"].startswith("/"))
                for item in detail["steps"]:
                    self.assertGreaterEqual(len(item["detail"].split()), 12)
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
                html = unescape(r.content.decode("utf-8"))
                self.assertIn(old_title, html)
                self.assertIn(field_title, html)
                self.assertIn('data-editorial="mojplaywin-original"', html)
                self.assertEqual(html.count('class="mpx-editorial-figure"'), 3)
                self.assertIn('href="https://mojplaywin.com' + path + '"', html)
                self.assertNotIn('href="https://zomorodmelal.ir' + path + '"', html)

    def test_anonymous_agents_page_hides_sensitive_staff_operations(self):
        response = self.client.get("/agents/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('id="mpx-staff-agent-operations"', response.content.decode("utf-8"))
        self.assertNotIn('href="/admin/core/agenttask/"', response.content.decode("utf-8"))

    def test_staff_agent_navigation_has_protected_known_paths_in_source(self):
        source = (ROOT / "core" / "templates" / "mojplaywin" / "section.html").read_text(encoding="utf-8")
        self.assertIn('request.user.is_staff', source)
        self.assertIn('href="/staff/command-center/"', source)
        self.assertIn('href="/admin/core/agent/"', source)

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

    def test_original_digital_assets_are_valid_safe_svg_and_referenced(self):
        from xml.etree import ElementTree

        names = ("digital-products.svg", "ai-workflow.svg", "blockchain-network.svg")
        for name in names:
            with self.subTest(name=name):
                path = HEROES / "site" / "mojplaywin-atelier" / name
                data = path.read_text(encoding="utf-8")
                root = ElementTree.fromstring(data)
                self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertIn("viewBox", root.attrib)
                self.assertNotIn("<script", data.lower())
                self.assertNotIn("http://", data.replace("http://www.w3.org/2000/svg", ""))
                self.assertNotIn("https://", data)
        store = (ROOT / "core" / "templates" / "mojplaywin" / "store.html").read_text(encoding="utf-8")
        brand = (ROOT / "core" / "templates" / "brands" / "mojplaywin" / "page.html").read_text(encoding="utf-8")
        self.assertIn("digital-products.svg", store)
        self.assertIn("ai-workflow.svg", brand)
        self.assertIn("blockchain-network.svg", brand)

    def test_agent_detail_is_educational_not_false_live_status(self):
        content = editorial_for("section", "agents")
        self.assertIsNotNone(content)
        self.assertIn("does not state that any specific", content["note"])
        self.assertIn("Domain ownership", " ".join(content["overview"]))
