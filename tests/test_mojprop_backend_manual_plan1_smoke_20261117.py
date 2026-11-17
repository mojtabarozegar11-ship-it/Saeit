"""Source-only safety tests for the manually authorized Plan 1 backend release.
Never calls a live URL, deploys, logs CSRF, mutates customer records or processes TRX.
"""
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT / ".github/workflows/mojprop-backend-controlled-release-20261115.yml"
ACTIVE=ROOT / "templates/moj-prop-v4/index.html"
ACCESSIBLE=ROOT / "core/mojprop_accessible_intake.py"
VIEW=ROOT / "core/mojprop_views.py"


class ManualRealPlanOneReleaseGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wf=WORKFLOW.read_text(encoding="utf-8")
        cls.home=ACTIVE.read_text(encoding="utf-8")
        cls.backend=ACCESSIBLE.read_text(encoding="utf-8")
        cls.views=VIEW.read_text(encoding="utf-8")

    def test_only_manual_workflow_can_release_backend(self):
        self.assertIn("  workflow_dispatch:", self.wf)
        self.assertIn("github.event_name == 'workflow_dispatch'", self.wf)
        self.assertNotIn("  pull_request:", self.wf)
        self.assertNotIn("  push:", self.wf)

    def test_owner_and_exact_main_commit_attested(self):
        for marker in ("github.actor == 'mojtabarozegar11-ship-it'",
                       "github.ref == 'refs/heads/main'",
                       "vars.MOJPROP_APPROVED_MAIN_SHA == github.sha",
                       '[[ "$REQUESTED_RELEASE_SHA" == "$GITHUB_SHA" ]]',
                       "github.run_attempt == 1"):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.wf)

    def test_full_restore_rollback_tenant_and_owner_gates_unchanged(self):
        for marker in ("inputs.owner_approval == 'OWNER_APPROVED'",
                       "vars.MOJPROP_BACKUP_RESTORE_VERIFIED == 'true'",
                       "vars.MOJPROP_ROLLBACK_VERIFIED == 'true'",
                       "vars.MOJPROP_TENANT_ISOLATION_VERIFIED == 'true'",
                       "needs: validate"):
            with self.subTest(marker=marker):
                self.assertIn(marker,self.wf)

    def test_obsolete_educational_marketing_is_not_required(self):
        self.assertNotIn('"See service prices"', self.wf)
        for marker in ('"MOJ-PROP-01"', '"PRELAUNCH"',
                       '"No wallet or payment collection now."',
                       'MOJPROP-STARTER30" not in home',
                       "'action=\"/moj-prop/checkout/' not in home"):
            with self.subTest(marker=marker):
                self.assertIn(marker,self.wf)
        self.assertIn("MOJ-PROP-01",self.home)
        self.assertNotIn("MOJPROP-STARTER30",self.home)

    def test_source_and_published_html_both_guard_correct_package_route(self):
        route="/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=moj-prop-01"
        self.assertGreaterEqual(self.wf.count(route),2)
        self.assertIn(route,self.home)

    def test_cannot_print_private_response_bytes_on_error(self):
        self.assertNotIn("head -c 300",self.wf)
        self.assertNotIn("MOJ_PROP_INTAKE_BODY=",self.wf)
        self.assertIn("PRIVATE_RESPONSE_BODY_WITHHELD=true",self.wf)
        self.assertNotIn("curl -d",self.wf)

    def test_nojs_get_check_requires_both_200_without_following_redirect(self):
        self.assertIn('intake_html_http="$(curl',self.wf)
        self.assertIn('status_html_http="$(curl',self.wf)
        self.assertIn("--max-redirs 0",self.wf)
        self.assertIn('[[ "$intake_html_http" != "200" || "$status_html_http" != "200" ]]',self.wf)
        self.assertIn("GET_ONLY=true; BUYER_POST=false; PAYMENT=false",self.wf)

    def test_nojs_html_and_status_backend_are_really_routed(self):
        self.assertIn("def request_form(request",self.backend)
        self.assertIn("def status_form(request",self.backend)
        self.assertIn("def mojprop_intake(request)",self.views)
        self.assertIn("def mojprop_receipt_status(request)",self.views)

    @classmethod
    def smoke_script(cls):
        pattern=(r'python3 - "\$RUNNER_TEMP/moj-prop-intake-html-private.html" '
                 r'"\$RUNNER_TEMP/moj-prop-status-html-private.html" <<\x27PY\x27'
                 r'\n(.*?)\n          PY')
        match=re.search(pattern,cls.wf,re.S)
        if match is None:
            raise AssertionError("Expected no-JS HTML post-deploy gate missing")
        return textwrap.dedent(match.group(1))

    def run_contract(self,*,intake_ok=True,status_ok=True,unsafe=False):
        body=(
            '<!doctype html><form method="post" '
            'action="/moj-prop-intake/?format=html">'
            '<input name="csrfmiddlewaretoken" value="synthetic-test">'
            '<input name="consent">'
            '<p>Prelaunch interest only: MOJ-PROP-01</p></form>'
        )
        status=(
            '<!doctype html><form method="post" '
            'action="/moj-prop-status/?format=html">'
            '<input name="csrfmiddlewaretoken" value="synthetic-test">'
            '<input name="receipt_token"></form>'
        )
        if not intake_ok: body=body.replace('name="consent"','name="other"')
        if not status_ok: status=status.replace('name="receipt_token"','name="other"')
        if unsafe: status+='<form method="get" action="/moj-prop-status/"></form>'
        with tempfile.TemporaryDirectory() as temp:
            a=Path(temp)/"intake.html"
            b=Path(temp)/"status.html"
            a.write_text(body,"utf-8")
            b.write_text(status,"utf-8")
            return subprocess.run(
                [sys.executable,"-c",self.smoke_script(),str(a),str(b)],
                capture_output=True,text=True,timeout=10,check=False,
            )

    def test_synthetic_nojs_smoke_passes_with_exact_intake_and_status(self):
        result=self.run_contract()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("MOJ_PROP_NOJS_BACKEND_GATE=PASS",result.stdout)
        self.assertNotIn("synthetic-test",result.stdout)

    def test_missing_consent_fails_closed_without_pii(self):
        result=self.run_contract(intake_ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("MOJ_PROP_NOJS_BACKEND_GATE=FAIL",result.stderr)
        self.assertNotIn("synthetic-test",result.stderr)

    def test_missing_private_status_token_fails_closed(self):
        result=self.run_contract(status_ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("status-private-token",result.stderr)

    def test_unsafe_get_bearer_form_fails_closed(self):
        result=self.run_contract(unsafe=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("unsafe form",result.stderr)


if __name__ == "__main__":
    unittest.main()
