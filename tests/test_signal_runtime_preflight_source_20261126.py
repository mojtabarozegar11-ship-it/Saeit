"""Static safety checks for the read-only Signal Desk runtime preflight."""

from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts/mpw_signal_runtime_preflight_20261126.py").read_text(
    encoding="utf-8"
)


class SignalRuntimePreflightSourceTests(TestCase):
    def test_preflight_is_read_only_and_checks_weekly_migration(self):
        self.assertIn("MigrationRecorder", SOURCE)
        self.assertIn("0005_align_weekly_signal_terms", SOURCE)
        self.assertIn('"read_only": True', SOURCE)
        self.assertIn('"public_signal_subscription_enabled": False', SOURCE)
        self.assertNotIn("migrate --", SOURCE)
        self.assertNotIn("objects.create(", SOURCE)
        self.assertNotIn("save(", SOURCE)
        self.assertNotIn("delete(", SOURCE)
