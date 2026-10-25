"""Safety regression: configuring the minute scheduler must never itself run a product."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy/install_factory_strict_serial_fullcycle_v1.sh"


class StrictSerialInstallerSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INSTALLER.read_text(encoding="utf-8")

    def test_installer_shell_syntax(self):
        result = subprocess.run(["bash", "-n", str(INSTALLER)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_approval_fails_closed_before_filesystem_preflight(self):
        env = os.environ.copy()
        env.pop("SAEIT_QC1000_INSTALL_APPROVED", None)
        result = subprocess.run(["bash", str(INSTALLER), "/does-not-exist"],
                                env=env, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("STRICT_SERIAL_INSTALL_APPROVAL_REQUIRED", result.stderr)

    def test_approved_path_passes_approval_gate_only(self):
        # An invalid source path must still fail, without reaching cron or file writes.
        env = os.environ.copy()
        env["SAEIT_QC1000_INSTALL_APPROVED"] = "1"
        result = subprocess.run(["bash", str(INSTALLER), "/does-not-exist"],
                                env=env, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("STRICT_SERIAL_INSTALL_APPROVAL_REQUIRED", result.stderr)

    def test_approval_guard_precedes_any_installer_writes(self):
        gate = self.source.index('SAEIT_QC1000_INSTALL_APPROVED:-')
        for mutation in ('install -d -m 700 "$backup"',
                         'install -m 600 "$source" "$temp"',
                         'crontab "$temp_cron"'):
            with self.subTest(mutation=mutation):
                self.assertLess(gate, self.source.index(mutation))

    def test_installer_is_configuration_only_not_a_product_tick(self):
        self.assertIn('--operations "$ops" --dry-run', self.source)
        self.assertNotIn('/usr/bin/timeout 56s "$python"', self.source)
        self.assertNotIn('echo STRICT_SERIAL_ACTIVE_ONE_ORDER_UNTIL_AUTHENTIC_QC1000',
                         self.source)
        self.assertIn('STRICT_SERIAL_CRON_CONFIGURED_RUNTIME_NOT_VERIFIED',
                      self.source)
        self.assertIn('/usr/bin/flock -n', self.source)
        self.assertIn('--require-scheduler-scope >>', self.source)


if __name__ == "__main__":
    unittest.main()
