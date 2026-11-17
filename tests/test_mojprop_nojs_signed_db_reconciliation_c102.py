"""C102 current-main regression: no-JS customer request AND independent DB restore.

All checks are source-only; none authenticates buyers, charges TRX, restores
a real database, or deploys a production service.
"""
import unittest
from pathlib import Path

from scripts import deploy_mojplaywin_moj_prop_backend as deployer
from scripts.mojprop_schema_preflight_c83 import MODULES, MIGRATIONS

ROOT = Path(__file__).resolve().parents[1]


class MojPropNoJsDbProofClosureTests(unittest.TestCase):
    def test_01_presenter_installed_before_importing_crm_view(self):
        files = list(deployer.REPLACE_FILES)
        self.assertIn(Path("core/mojprop_accessible_intake.py"), files)
        self.assertLess(files.index(Path("core/mojprop_accessible_intake.py")),
                        files.index(Path("core/mojprop_views.py")))

    def test_02_presenter_is_in_schema_closure(self):
        self.assertIn("core/mojprop_accessible_intake.py", MODULES)

    def test_03_private_db_verifier_never_replaced_in_live_app(self):
        for name in ("scripts/mojprop_db_release_evidence.py",
                     "scripts/mojprop_live_database_identity_c85.py"):
            self.assertIn(Path(name), deployer.ALL_FILES)
            self.assertNotIn(Path(name), deployer.REPLACE_FILES)

    def test_04_independent_proof_is_required_before_backup_root_creation(self):
        code = (ROOT / "scripts/deploy_mojplaywin_moj_prop_backend.py").read_text()
        self.assertLess(code.index("require_independent_db_restore(run_id, commit, staged_root)"),
                        code.index("backup = BACKUP_ROOT / run_id"))
        self.assertLess(code.index('closure = check_schema_closure(ROOT, staged_root)'),
                        code.index("require_independent_db_restore(run_id, commit, staged_root)"))

    def test_05_migration_target_is_not_0046_or_unknown(self):
        self.assertEqual(MIGRATIONS[-1], "0047_mpw_guest_email_recovery")
        code = (ROOT / "scripts/deploy_mojplaywin_moj_prop_backend.py").read_text()
        self.assertIn('migration_target = "0047_mpw_guest_email_recovery"', code)
        self.assertIn('"core", migration_target, "--noinput"', code)
        self.assertIn("schema target is stale; release denied", code)

    def test_06_full_manual_bundle_contains_native_page_and_signed_proof(self):
        path = ROOT / ".github/workflows/mojprop-backend-controlled-release-20261115.yml"
        workflow = path.read_text()
        pack = workflow.split("- name: Package only Moj Prop installer and page", 1)[1]
        pack = pack.split("- name: Upload isolated Moj Prop package", 1)[0]
        for name in ("core/mojprop_accessible_intake.py",
                     "core/mojprop_views.py",
                     "scripts/mojprop_db_release_evidence.py",
                     "scripts/mojprop_live_database_identity_c85.py"):
            self.assertIn(name, pack)

    def test_07_html_fallback_still_visible_on_main_commercial_landing(self):
        source = (ROOT / "templates/moj-prop-v4/index.html").read_text()
        self.assertIn(
            'href="/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=moj-prop-01"',
            source,
        )
        self.assertNotIn("MOJPROP-STARTER30", source)
        self.assertIn("<noscript>", source)

    def test_08_no_js_view_uses_real_existing_idempotent_crm_path(self):
        code = (ROOT / "core/mojprop_views.py").read_text()
        self.assertIn("def _mojprop_intake_api(request)", code)
        self.assertIn("api_response = _mojprop_intake_api(request)", code)
        self.assertIn("return created_receipt(result, reused=", code)
        self.assertIn("def _keyed_request_id(", code)
        self.assertIn("return _intake_success(request_obj, reused=False)", code)

    def test_09_signed_private_status_uses_post_not_get_token(self):
        code = (ROOT / "core/mojprop_views.py").read_text()
        self.assertIn('request.GET.getlist("format")', code)
        self.assertIn('if request.GET.getlist("receipt_token")', code)
        self.assertIn('return status_result(request_id, public_status_text(stage))', code)

    def test_10_unsafe_auto_publish_is_still_forbidden(self):
        workflow = (ROOT / ".github/workflows/mojprop-backend-controlled-release-20261115.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("inputs.owner_approval == 'OWNER_APPROVED'", workflow)
        self.assertIn("vars.MOJPROP_TENANT_ISOLATION_VERIFIED == 'true'", workflow)
        self.assertNotIn("on: push", workflow)


if __name__ == "__main__":
    unittest.main()
