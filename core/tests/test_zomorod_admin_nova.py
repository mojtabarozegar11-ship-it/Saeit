"""Check Zomorod-only Django admin theme leaves other admin hosts unchanged."""
from pathlib import Path
from django.test import SimpleTestCase, override_settings
from django.test.client import RequestFactory
from django.template.loader import render_to_string

SRC = Path(__file__).resolve().parents[2] / "templates/admin/base_site.html"


class ZomorodAdminNovaTests(SimpleTestCase):
    def test_admin_override_keeps_all_native_admin_components(self):
        source = SRC.read_text(encoding="utf-8")
        self.assertIn('{% extends "admin/base.html" %}', source)
        self.assertIn('block branding', source)
        self.assertIn('block extrastyle', source)
        self.assertIn('block nav-global', source)
        for item in ("Django", "zm-nova-brand", "login #container", "#changelist", "#nav-sidebar",
                     "prefers-reduced-motion", "focus-visible"):
            with self.subTest(item=item):
                self.assertIn(item, source)
        self.assertNotIn("DROP TABLE", source)

    @override_settings(ALLOWED_HOSTS=["zomorodmelal.ir", "www.zomorodmelal.ir", "mojplaywin.com"])
    def test_owner_domain_only_renders_nova_style(self):
        rf = RequestFactory()
        args = {"title": "مدیریت", "site_header": "Site Administration",
                "site_title": "Admin", "available_apps": [], "has_permission": True}
        for domain in ("zomorodmelal.ir", "www.zomorodmelal.ir"):
            with self.subTest(domain=domain):
                request = rf.get("/admin/", HTTP_HOST=domain)
                rendered = render_to_string("admin/base_site.html", {**args, "request": request}, request=request)
                self.assertIn("میز مدیریت زمرد ملل", rendered)
                self.assertIn("zm-nova-brand", rendered)
                self.assertIn('href="/agents/"', rendered)
                self.assertIn("prefers-reduced-motion", rendered)
        request = rf.get("/admin/", HTTP_HOST="mojplaywin.com")
        result = render_to_string("admin/base_site.html", {**args, "request": request}, request=request)
        self.assertNotIn("زمرد ملل", result)
        self.assertNotIn("zm-nova-brand", result)
        self.assertNotIn("prefers-reduced-motion", result)
