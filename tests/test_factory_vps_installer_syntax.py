"""Static deployment QA: validate the autonomous VPS installer before release."""
from pathlib import Path
import shutil
import subprocess
import unittest


class VPSProductInstallerTests(unittest.TestCase):
    def test_installer_is_valid_bash(self):
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash not installed")
        script = Path(__file__).resolve().parents[1] / "deploy" / "install_autonomous_factory_products.sh"
        result = subprocess.run([bash, "-n", str(script)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_installer_does_not_touch_live_storefronts_or_orders(self):
        script = (Path(__file__).resolve().parents[1] /
                  "deploy" / "install_autonomous_factory_products.sh").read_text(encoding="utf-8")
        self.assertIn("SAEIT_AUTONOMOUS_PRODUCTS_V2", script)
        self.assertIn("factory_vps_product_cycle.py", script)
        self.assertIn("factory_evidence_quality.py", script)
        self.assertIn('test -f "$repo/scripts/factory_evidence_quality.py"', script)
        self.assertIn("PUBLISHING_ENABLED=false", script)
        self.assertIn("ORDER_REQUIRED=false", script)
        self.assertNotIn("core_order", script)

    def test_deployment_preflight_enforces_private_path_safety_and_disk_reserve(self):
        """Never cut over when the runtime can escape a protected directory or fill disk."""
        script = (Path(__file__).resolve().parents[1] /
                  "deploy/install_autonomous_factory_products.sh").read_text(encoding="utf-8")
        self.assertIn("FACTORY_PRODUCT_RUNTIME_PATH_UNSAFE", script)
        self.assertIn('[[ -L "$protected_path" ]]', script)
        self.assertIn('df -Pk "$base/private"', script)
        self.assertIn("free_kib < 3145728", script)
        self.assertIn("FACTORY_PRODUCT_DEPLOY_DISK_RESERVE_HOLD", script)
        self.assertIn("FACTORY_FLAGSHIP_SOURCE_INSTALLED_BYTE_FOR_BYTE=PASS", script)
        self.assertIn("FACTORY_FLAGSHIP_SOURCE_ACTIVATION_MISMATCH", script)
        self.assertIn("cmp -s", script)

    def test_manufacturer_policy_dependency_survives_vps_install_and_transport(self):
        """Prevent deploying a maker that cannot import its private passport policy."""
        source = Path(__file__).resolve().parents[1]
        installer = (source / "deploy/install_autonomous_factory_products.sh").read_text(encoding="utf-8")
        workflow = (source / ".github/workflows/vps-autonomous-product-install.yml").read_text(encoding="utf-8")
        maker = (source / "scripts/factory_product_maker.py").read_text(encoding="utf-8")
        policy = "factory_personal_owner_passport_policy_20261020.py"
        self.assertIn("with_name(", maker)
        self.assertIn('"' + policy + '"', maker)
        self.assertTrue((source / "scripts" / policy).is_file())
        self.assertIn('test -f "$repo/scripts/' + policy + '"', installer)
        self.assertIn('test ! -L "$repo/scripts/' + policy + '"', installer)
        self.assertIn('for f in factory_product_maker.py ' + policy, installer)
        self.assertIn('"$scripts/' + policy + '"', installer)
        self.assertIn('scripts/' + policy + ' scripts/factory_product_rework.py', workflow)
        self.assertEqual(workflow.count('      - "scripts/' + policy + '"'), 2)
        self.assertIn("python -B -m unittest discover -s tests -p 'test_factory_private_passport_20261020.py'", workflow)
        self.assertIn("python3 -m unittest discover -s tests -p 'test_factory_private_passport_20261020.py'", workflow)
        self.assertNotIn('PUBLISHING_ENABLED=true', installer)

    def test_manual_or_owner_requested_gated_deployment_is_packaged(self):
        source = Path(__file__).resolve().parents[1]
        wf = (source / ".github/workflows/vps-autonomous-product-install.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/factory_evidence_quality.py", wf)
        self.assertIn("workflow_dispatch:", wf)
        self.assertIn("branches: [main]", wf)
        self.assertIn("[approved-factory-unlimited-builds-20261019]", wf)
        self.assertIn("product_recipes/**", wf)

    def test_customer_acceptance_module_is_in_real_vps_test_archive(self):
        """Avoid a green hosted CI but 19 failed runtime tests on the VPS."""
        source=Path(__file__).resolve().parents[1]
        wf=(source/".github/workflows/vps-autonomous-product-install.yml").read_text(encoding="utf8")
        runtime=(source/"scripts/factory_vps_product_cycle.py").read_text(encoding="utf8")
        dependency="factory_verified_customer_cycle_20261021.py"
        self.assertIn('SCRIPTS / "'+dependency+'"',runtime)
        self.assertTrue((source/"scripts"/dependency).is_file())
        self.assertIn('scripts/'+dependency+' scripts/factory_personal_owner_passport_policy_20261020.py',wf)
        self.assertIn('VPS_FACTORY_REQUIRED_CUSTOMER_MODULE_STAGED=PASS',wf)

    def test_legacy_upgrade_regression_helper_is_staged_and_importable(self):
        """VPS unittest discovery must see the sibling tests helper package."""
        source=Path(__file__).resolve().parents[1]
        wf=(source/".github/workflows/vps-autonomous-product-install.yml").read_text(encoding="utf8")
        self.assertTrue((source/"tests/test_factory_source_evolution.py").is_file())
        self.assertIn('tests/test_factory_vps_product_cycle.py tests/test_factory_source_evolution.py',wf)
        self.assertIn('VPS_FACTORY_LEGACY_SOURCE_EVOLUTION_FIXTURE_STAGED=PASS',wf)
        self.assertIn('cd "$HOME/factory-runtime/operations/product-deploy-${{ github.sha }}" &&',wf)

    def test_vps_deployment_budget_covers_measured_product_reinspection(self):
        """The live 12-minute window previously cancelled after actual factory work."""
        source=Path(__file__).resolve().parents[1]
        wf=(source/".github/workflows/vps-autonomous-product-install.yml").read_text(encoding="utf8")
        self.assertIn('timeout-minutes: 22',wf)
        self.assertIn('if engineering_targets_exist():',wf)
        self.assertIn('FACTORY_ENGINEERING_TICKS_RUN=',wf)


if __name__ == "__main__":
    unittest.main()
