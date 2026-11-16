"""Fail closed against accidental factory restart on scheduled GitHub workflows.

These tests read version-controlled text only. They do not access any host.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONTINUITY = ROOT / ".github/workflows/vps-factory-production-continuity.yml"
PAUSE = ROOT / ".github/workflows/vps-factory-low-disk-pause-20261029.yml"
READ_ONLY_RELAY = ROOT / ".github/workflows/vps-to-cpanel-ssh-readonly-20261112.yml"


class FactoryConnectivityPreservationTests(unittest.TestCase):
    def test_unattended_hourly_legacy_recovery_cannot_run(self):
        source = CONTINUITY.read_text(encoding="utf8")
        self.assertIn("HARD SAFETY HOLD (2026-11-16)", source)
        self.assertNotIn('cron: "13 * * * *"', source)
        self.assertNotRegex(source, r"(?m)^\s*schedule:\s*$")
        self.assertRegex(source, r"(?m)^\s*ensure:\s*$")
        ensure = source.split("\n  ensure:\n", 1)[1]
        self.assertRegex(ensure, r"(?m)^\s*if:\s*\$\{\{\s*false\s*\}\}\s*$")

    def test_specialized_read_only_and_low_disk_jobs_remain_guarded(self):
        source = CONTINUITY.read_text(encoding="utf8")
        header = source.split("\n  ensure:\n", 1)[0]
        self.assertIn("pause-loop-low-disk:", header)
        self.assertIn("audit-readonly:", header)
        self.assertIn("github.event_name == 'push'", header)
        self.assertIn("[factory-pause-low-disk-loop-20261029]", header)
        self.assertIn("[factory-readonly-audit-20261029]", header)
        self.assertIn("cancel-in-progress: false", source)

    def test_disk_pressure_safety_pause_not_weakened(self):
        source = PAUSE.read_text(encoding="utf8")
        for invariant in (
            "reserve_kib=524288",
            "FACTORY_AUTO_RESUME=false",
            "FACTORY_LOW_DISK_PAUSE=production_schedulers_paused",
        ):
            self.assertIn(invariant, source)

    def test_existing_read_only_cpanel_relay_requires_pinned_ssh(self):
        source = READ_ONLY_RELAY.read_text(encoding="utf8")
        self.assertIn("runs-on: [self-hosted, factory-vps]", source)
        self.assertIn("StrictHostKeyChecking=yes", source)
        self.assertIn("BatchMode=yes", source)
        self.assertIn("IdentitiesOnly=yes", source)
        self.assertIn("SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04", source)


if __name__ == "__main__":
    unittest.main()
