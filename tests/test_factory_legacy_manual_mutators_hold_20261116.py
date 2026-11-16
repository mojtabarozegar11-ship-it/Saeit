"""Offline safety contract: old VPS factory mutation entrypoints stay paused.

Only inspect checked-in text; no SSH, network, customer data or live process.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    ".github/workflows/vps-factory-persistence.yml": "configure",
    ".github/workflows/vps-factory-controlled-restart.yml": "restart",
    ".github/workflows/vps-factory-provider-recovery.yml": "recover",
}


class LegacyFactoryManualRestartSafety(unittest.TestCase):
    def test_all_legacy_mutator_jobs_hard_held(self):
        for rel, job in FILES.items():
            with self.subTest(workflow=rel):
                content = (ROOT / rel).read_text(encoding="utf-8")
                self.assertIn("HARD SAFETY HOLD 2026-11-16", content)
                match = re.search(
                    r"(?m)^  " + re.escape(job) + r":\n(?:    #[^\n]*\n)*"
                    r"    if: \$\{\{ false \}\}\n"
                    r"    runs-on: ubuntu-latest",
                    content,
                )
                self.assertIsNotNone(match)
                self.assertIn("contents: read", content)

    def test_previous_mutator_scripts_remain_inert_but_not_destroyed(self):
        expected = {
            "configure": ["SAEIT_FACTORY_AUTOSTART", "crontab"],
            "restart": ["vps-only-loop.sh", "kill -TERM"],
            "recover": ["sqlite3", "FACTORY_RESEARCH_PROVIDER"],
        }
        for path, job in FILES.items():
            source = (ROOT / path).read_text(encoding="utf-8")
            with self.subTest(job=job):
                for marker in expected[job]:
                    self.assertIn(marker, source)
                self.assertIn("if: ${{ false }}", source)

    def test_existing_factory_hourly_auto_recovery_still_disabled(self):
        source = (ROOT / ".github/workflows/vps-factory-production-continuity.yml").read_text()
        self.assertNotIn('cron: "13 * * * *"', source)
        self.assertRegex(source, r"(?m)^  ensure:\n(?:    #[^\n]*\n)*    if: \$\{\{ false \}\}")

    def test_existing_owner_pinned_cpanel_relay_is_untouched(self):
        relay = (ROOT / ".github/workflows/vps-to-cpanel-ssh-readonly-20261112.yml").read_text()
        self.assertIn("runs-on: [self-hosted, factory-vps]", relay)
        self.assertIn("StrictHostKeyChecking=yes", relay)
        self.assertIn("BatchMode=yes", relay)
        self.assertIn("SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04", relay)


if __name__ == "__main__":
    unittest.main()
