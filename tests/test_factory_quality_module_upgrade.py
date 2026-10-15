"""Guardrails for installing the research-quality gate in an active private factory."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
UPGRADE = ROOT / "deploy/upgrade_factory_product_quality_gate.sh"
INSTALL = ROOT / "deploy/install_autonomous_factory_products.sh"
WORKFLOW = ROOT / ".github/workflows/vps-autonomous-product-install.yml"


class QualityModuleUpgradeTests(unittest.TestCase):
    def test_bash_syntax(self):
        for script in (UPGRADE, INSTALL):
            with self.subTest(script=script.name):
                run = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True, timeout=10)
                self.assertEqual(run.returncode, 0, run.stderr)

    def test_missing_dependency_is_packaged_by_regular_installer(self):
        content = INSTALL.read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('test -f "$repo/scripts/factory_evidence_quality.py"', content)
        self.assertIn("factory_evidence_quality.py", content)
        self.assertIn("scripts/factory_evidence_quality.py", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("branches: [main]", workflow)

    def test_upgrade_is_guarded_and_can_roll_back_code(self):
        s = UPGRADE.read_text(encoding="utf-8")
        for marker in (
            '[[ "$(id -un)" == "githubops"',
            '"$ops/autonomous-product-cycle.lock"',
            '"$private/.production-cycle.lock"',
            "FACTORY_PRODUCT_CYCLE_BUSY_NO_MODIFICATIONS",
            "FACTORY_DISPOSABLE_PRODUCT_CYCLE_AND_RESEARCH_GATE_PASSED",
            "FACTORY_VPS_LIVE_PRODUCT_RESEARCH_GATE_VERIFIED",
            "rollback_needed=true", "trap rollback EXIT",
            "FACTORY_QUALITY_DEPLOY_ROLLED_BACK",
            "factory_evidence_quality.py",
            "factory_autonomous_portfolio.py",
            "factory_vps_product_cycle.py",
            'test "$old_cron" =',
            'FACTORY_PRIVATE_QUALITY_GATE_DEPLOY_SUCCEEDED',
        ):
            self.assertIn(marker, s)
        for prohibited in (
            "crontab \"$tmp\"",
            "systemctl restart",
            "rm -rf",
            "sudo ",
            "ALTER TABLE",
            "UPDATE core_product",
            "core_order",
            "publish_to_store",
            "FactoryRun.objects.update",
        ):
            self.assertNotIn(prohibited, s)

    def test_upgrade_only_touches_isolated_scripts(self):
        script = UPGRADE.read_text(encoding="utf-8")
        self.assertIn('target="$runtime/scripts"', script)
        self.assertIn('private="$base/private/autonomous-product-cycle"', script)
        self.assertIn('db="$base/private/factory-fresh-isolated.sqlite3"', script)
        self.assertNotIn("zomorodmelal.ir", script)
        self.assertNotIn("mojplaywin.com", script)
        self.assertNotIn("zohal.pws", script)


if __name__ == "__main__":
    unittest.main()
