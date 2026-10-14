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
        self.assertIn("PUBLISHING_ENABLED=false", script)
        self.assertIn("ORDER_REQUIRED=false", script)
        self.assertNotIn("core_order", script)


if __name__ == "__main__":
    unittest.main()
