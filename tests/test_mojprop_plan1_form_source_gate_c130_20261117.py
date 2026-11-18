"""C130: exact Plan1 GET/POST source contract. No live POST or payment."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.mojprop_plan1_form_source_gate_c130 import (
    FORM, _canonical_links, _source_routes, _view_guards, evaluate, KEYS,
)

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/mojprop_plan1_form_source_gate_c130.py"

GOOD_HTML = (
    '<html><a href="/moj-prop-interest/form/">EN</a>'
    '<a href="/moj-prop-interest/form/?lang=fa">FA</a></html>'
)
GOOD_URLS = (
    'from core.moj_prop_views import moj_prop_interest, moj_prop_interest_form\n'
    'urlpatterns = [path("moj-prop-interest/form/", moj_prop_interest_form), '
    'path("moj-prop-interest/", moj_prop_interest)]\n'
)
GOOD_VIEWS = '''
@never_cache
@csrf_protect
def moj_prop_interest_form(request):
    request.get_host()
    request.is_secure()
    request.GET.get("lang")
    choices = ("GET", "HEAD")
    return HttpResponse(status=400)

@csrf_protect
@require_POST
def moj_prop_interest(request):
    request.get_host()
    request.is_secure()
    contact_consent = "contact_consent"
    sku = "MOJ-PROP-01"
    PropInterest
'''
GOOD_TEMPLATE = (
    '<form action="/moj-prop-interest/" method="post">'
    '{% csrf_token %}<input name="email">'
    '<input name="contact_consent">MOJ-PROP-01</form>'
)
GOOD_MODEL = "class PropInterest(models.Model):\n    pass\n"
GOOD_MIGRATION = 'migrations.CreateModel(name="PropInterest")\n'


def _put(root: Path, name: str, contents: str):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(contents, "utf-8")
    return target


def make_complete_fixture(root: Path):
    for item in ("templates/moj-prop/contact/index.html",
                 "templates/moj-prop-v4/index.html"):
        _put(root, item, GOOD_HTML)
    _put(root, "config/urls.py", GOOD_URLS)
    _put(root, "core/moj_prop_views.py", GOOD_VIEWS)
    _put(root, "core/templates/mojplaywin/moj_prop_interest_form_d.html", GOOD_TEMPLATE)
    _put(root, "prop_firm/lead_models.py", GOOD_MODEL)
    _put(root, "prop_firm/migrations/0008_prospect_contact_intake.py", GOOD_MIGRATION)


class CanonicalFormQueryAndReleaseGateTests(unittest.TestCase):
    def test_current_branch_has_safe_correct_en_fa_links(self):
        evidence = evaluate(ROOT)
        self.assertTrue(evidence["landing_and_contact_query_contract"], evidence)

    def test_current_parent_branch_does_not_fabricate_dedicated_backend(self):
        # The actual dedicated form is on separate unmerged canonical #2310.
        report = evaluate(ROOT)
        self.assertFalse(report["source_ready"])
        self.assertFalse(report["dedicated_get_route_mapped"])
        self.assertFalse(report["dedicated_post_route_mapped"])

    def test_complete_source_fixture_is_accepted_without_claiming_live(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            make_complete_fixture(root)
            report = evaluate(root)
            self.assertEqual(tuple(report), KEYS)
            self.assertTrue(all(report.values()), report)

    def test_legacy_blueprint_query_returns_false(self):
        broken = GOOD_HTML.replace(
            FORM + '?lang=fa',
            FORM + '?service=blueprint&amp;package=moj-prop-01'
        )
        self.assertFalse(_canonical_links(broken))

    def test_extra_buyer_query_is_rejected(self):
        for injection in (
            '?lang=fa&email=buyer%40invalid.test',
            '?lang=fa&token=private',
            '?service=blueprint',
            '?package=moj-prop-01',
            '?lang=ar',
            '?lang=fa&lang=fa',
            '?lang=fa&lang=en',
            '?lang=',
            '?email=buyer',
            '?lang=fa#private',
            '?lang=fa%26wallet%3Dsecret',
        ):
            with self.subTest(injection=injection):
                html = GOOD_HTML.replace(FORM + "?lang=fa", FORM + injection)
                self.assertFalse(_canonical_links(html))

    def test_http_absolute_or_protocol_relative_candidate_rejected(self):
        for prefix in ("https://mojplaywin.com", "//evil.invalid"):
            with self.subTest(prefix=prefix):
                self.assertFalse(_canonical_links(GOOD_HTML.replace(
                    'href="/moj-prop-interest/form/"',
                    f'href="{prefix}/moj-prop-interest/form/"'
                )))

    def test_missing_or_extra_candidates_are_rejected(self):
        self.assertFalse(_canonical_links("<html>No lead link</html>"))
        self.assertFalse(_canonical_links(GOOD_HTML + GOOD_HTML))
        self.assertFalse(_canonical_links(GOOD_HTML.replace("lang=fa", "lang=en")))
        self.assertFalse(_canonical_links(GOOD_HTML.replace("?lang=fa", "")))

    def test_post_only_route_must_not_be_substituted_for_get(self):
        a, b = _source_routes(GOOD_URLS)
        self.assertTrue(a and b)
        self.assertEqual(_source_routes(GOOD_URLS.replace(
            'path("moj-prop-interest/form/", moj_prop_interest_form)',
            'path("moj-prop-interest/form/", moj_prop_interest)'
        )), (False, True))

    def test_view_must_protect_csrf_and_method(self):
        self.assertTrue(_view_guards(GOOD_VIEWS))
        for fragment in ("@csrf_protect", "@require_POST", "request.is_secure()",
                         'status=400', "contact_consent", "PropInterest"):
            with self.subTest(missing=fragment):
                self.assertFalse(_view_guards(GOOD_VIEWS.replace(fragment, "REMOVED")))

    def test_symlinked_model_never_counts_as_valid_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            make_complete_fixture(root)
            target = root / "prop_firm" / "lead_models.py"
            other = root / "outside.txt"
            other.write_text(GOOD_MODEL, "utf-8")
            target.unlink()
            target.symlink_to(other)
            self.assertFalse(evaluate(root)["consent_model_and_migration_present"])

    def test_each_missing_component_blocks_release(self):
        items = (
            "config/urls.py", "core/moj_prop_views.py",
            "core/templates/mojplaywin/moj_prop_interest_form_d.html",
            "prop_firm/lead_models.py",
            "prop_firm/migrations/0008_prospect_contact_intake.py",
            "templates/moj-prop/contact/index.html",
            "templates/moj-prop-v4/index.html",
        )
        for missing in items:
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                make_complete_fixture(root)
                (root / missing).unlink()
                self.assertFalse(evaluate(root)["source_ready"])

    def test_runtime_source_audit_exits_zero_but_never_claims_live(self):
        p = subprocess.run([sys.executable, str(RUNNER)], cwd=ROOT,
                           text=True, capture_output=True, timeout=7)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("MOJPROP_C130_SOURCE_READY=false", p.stdout)
        self.assertIn("MOJPROP_C130_LIVE_PASSENGER_PARITY_PROVEN=false", p.stdout)
        self.assertIn("MOJPROP_C130_PAYMENT_OR_DEPLOYMENT=false", p.stdout)
        self.assertNotIn("buyer@", p.stdout)

    def test_release_preflight_returns_nonzero_when_route_unmounted(self):
        p = subprocess.run([sys.executable, str(RUNNER), "--require-source-ready"],
                           cwd=ROOT, text=True, capture_output=True, timeout=7)
        self.assertEqual(p.returncode, 3, p.stdout)
        self.assertIn("MOJPROP_C130_SOURCE_READY=false", p.stdout)

    def test_no_customer_action_or_external_network_in_source_gate(self):
        code = RUNNER.read_text("utf-8")
        for forbidden in ("requests.post(", "smtplib", "urllib.request", "subprocess.",
                          "objects.create(", "os.environ", "SECRET_KEY", "create_invoice"):
            self.assertNotIn(forbidden, code)
        self.assertTrue(code.count("print(") <= 6)


if __name__ == "__main__":
    unittest.main()
