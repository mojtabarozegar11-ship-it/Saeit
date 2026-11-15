"""Protect Moj Prop live catalog conversion from the actual 404 smoke bug.

GitHub's 2026-11-15 deploy job hit 404 because the HTML/CI probe used
/moj-prop-intake/ while the pinned Django backend registers /moj-prop-intake/.
This is source parity, not a live deploy test.
"""
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1]
CANONICAL = "/moj-prop-intake/"
BAD = "/moj-prop/not-a-real-intake/"


class MojPropCanonicalIntakeRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (BASE / "templates/moj-prop-v4/index.html").read_text(encoding="utf-8")
        cls.workflow = (BASE / ".github/workflows/mojplaywin-moj-prop-deploy.yml").read_text(encoding="utf-8")
        cls.installer = (BASE / "scripts/deploy_mojplaywin_moj_prop_backend.py").read_text(encoding="utf-8")

    def test_public_form_posts_to_registered_url(self):
        self.assertIn("const endpoint='/moj-prop-intake/'", self.html)

    def test_smoke_checks_backend_registered_url(self):
        self.assertIn("https://mojplaywin.com/moj-prop-intake/", self.workflow)

    def test_local_django_requestfactory_uses_identical_route(self):
        self.assertIn("RequestFactory().get('/moj-prop-intake/'", self.workflow)

    def test_django_client_smoke_uses_identical_route(self):
        self.assertIn("client.get('/moj-prop-intake/'", self.workflow)

    def test_url_resolver_uses_identical_route(self):
        self.assertIn("resolve('/moj-prop-intake/'", self.workflow)

    def test_backend_installer_registers_identical_route(self):
        self.assertIn('path("moj-prop/intake/"', self.installer)

    def test_html_does_not_ask_for_unregistered_endpoint(self):
        self.assertNotIn(BAD, self.html)

    def test_workflow_does_not_probe_unregistered_endpoint(self):
        self.assertNotIn(BAD, self.workflow)

    def test_smoke_never_changes_customer_order(self):
        self.assertIn('payload.get("service") != "moj-prop-intake"', self.workflow)
        self.assertIn("moj_prop_backend_deploy=", self.workflow)
