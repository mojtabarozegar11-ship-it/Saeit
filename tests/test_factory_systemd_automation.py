import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FactorySystemdAutomationTests(unittest.TestCase):
    def test_shell_files_are_syntactically_valid(self):
        for path in (
            ROOT / "deploy/install_factory_systemd_automation.sh",
            ROOT / "scripts/factory-runtime-watchdog.sh",
        ):
            result = subprocess.run(["bash", "-n", str(path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_install_requires_explicit_approval_before_mutation(self):
        script = ROOT / "deploy/install_factory_systemd_automation.sh"
        result = subprocess.run(
            ["bash", str(script)],
            env={k: v for k, v in os.environ.items()
                 if k != "SAEIT_FACTORY_SYSTEMD_INSTALL_APPROVED"},
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FACTORY_SYSTEMD_INSTALL_APPROVAL_REQUIRED", result.stderr)

    def test_units_are_persistent_and_one_product_only(self):
        cycle = (ROOT / "deploy/systemd/saeit-factory-cycle.timer").read_text()
        watchdog = (ROOT / "deploy/systemd/saeit-factory-watchdog.timer").read_text()
        service = (ROOT / "deploy/systemd/saeit-factory-cycle.service").read_text()
        self.assertIn("Persistent=true", cycle)
        self.assertIn("OnUnitActiveSec=1min", cycle)
        self.assertIn("Persistent=true", watchdog)
        self.assertIn("SAEIT_FACTORY_AUTORUN_ENABLED=1", service)


if __name__ == "__main__":
    unittest.main()
