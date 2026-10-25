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


    def _run_embedded_cron_preflight(self, cron):
        marker = "SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025"
        prefix = "printf '%s\\n' \"$cron_snapshot\" | python3 -B -c '"
        suffix = "' \"$new_marker\" \"${legacy_markers[@]}\""
        code = self.source.split(prefix, 1)[1].split(suffix, 1)[0]
        return subprocess.run(
            ["python3", "-B", "-c", code, marker,
             "SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1",
             "--SHARED-MARKERS--", "SAEIT_FACTORY_STAGE2_RESEARCH_V1"],
            input=cron, capture_output=True, text=True, timeout=10)

    def test_cron_and_timer_inventory_before_any_worker_mutation(self):
        preflight = self.source.index('cron_snapshot="$(crontab -l)"')
        timers = self.source.index('systemctl list-timers --all')
        check = self.source.index("STRICT_SERIAL_UNMARKED_COMPETING_PRODUCER")
        lock = self.source.index('exec 8>"$ops/.strict-serial-installer.lock"')
        backup = self.source.index('install -d -m 700 "$backup"')
        worker = self.source.index('install -m 600 "$source" "$temp"')
        self.assertTrue(preflight < timers < check < lock < backup < worker)

    def test_preflight_allows_known_legacy_and_one_valid_serial(self):
        known = ("* * * * * /ops/agri200-autonomous-closed-loop.py "
                 "# SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1\n")
        self.assertEqual(self._run_embedded_cron_preflight(known).returncode, 0)
        serial = ("* * * * * /ops/strict-serial-fullcycle-v1.py "
                  "# SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025\n")
        self.assertEqual(self._run_embedded_cron_preflight(serial).returncode, 0)

    def test_preflight_rejects_unknown_and_duplicate_minute_producers(self):
        serial = ("* * * * * /ops/strict-serial-fullcycle-v1.py "
                  "# SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025\n")
        cases = (
            ("* * * * * /ops/factory-minute-runner.sh\n",
             "UNMARKED_COMPETING_PRODUCER"),
            (serial + serial, "DUPLICATE_MINUTE_MARKER"),
            (serial.replace("* * * * *", "23 * * * *"),
             "UNRECOGNIZED_EXISTING_SCHEDULE"),
        )
        for cron, expected in cases:
            with self.subTest(expected=expected):
                result = self._run_embedded_cron_preflight(cron)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)


if __name__ == "__main__":
    unittest.main()
