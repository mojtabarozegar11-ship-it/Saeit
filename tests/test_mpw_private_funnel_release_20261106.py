"""Independent, offline publish/rollback checks: no production I/O."""
from pathlib import Path
import importlib.util
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts/mpw_private_funnel_guarded_release_20261106.py"
spec = importlib.util.spec_from_file_location("mpw_private_funnel_release_test", path)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseChecks(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.live = self.root / "live"
        self.live.mkdir()
        self.stage = self.root / "stage"
        (self.stage / "services").mkdir(parents=True)
        self.guest = self.live / "guest.py"
        self.guest.write_bytes(b"# current live guest\n")
        self.settings = self.live / "settings.py"
        self.settings.write_text(
            '# MPW_CAPTURE_ONLY_20261105\n'
            'MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED = True\n'
            'MPW_GUEST_RECOVERY_ENABLED = False\n'
            'MPW_GUEST_RECOVERY_EMAIL_APPROVED = False\n', encoding="utf8")
        self.metrics = self.live / "metrics.py"
        (self.stage / "services/mpw_trx_guest_commerce.py").write_bytes(
            (ROOT / "services/mpw_trx_guest_commerce.py").read_bytes())
        (self.stage / "services/mpw_checkout_funnel.py").write_bytes(
            (ROOT / "services/mpw_checkout_funnel.py").read_bytes())
        self.patches = (
            patch.object(release, "GUEST", self.guest),
            patch.object(release, "SETTINGS", self.settings),
            patch.object(release, "METRICS", self.metrics),
            patch.object(release, "BACKUPS", self.root / "backups"),
            patch.object(release, "GUEST_BEFORE", release.sha(self.guest.read_bytes())),
            patch.object(release, "guard_host", lambda: None),
        )
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_release_and_verify_preserves_private_backups(self):
        original_guest = self.guest.read_bytes()
        original_settings = self.settings.read_bytes()
        with patch.object(release, "restart", lambda: None):
            release.publish(self.stage, "42120000000")
        self.assertEqual(release.sha(self.guest.read_bytes()), release.GUEST_AFTER)
        self.assertEqual(release.sha(self.metrics.read_bytes()), release.METRICS_AFTER)
        self.assertEqual((self.root / "backups/42120000000/guest.before.py").read_bytes(),
                         original_guest)
        self.assertEqual((self.root / "backups/42120000000/settings.before.py").read_bytes(),
                         original_settings)
        self.assertIn(release.MARKER, self.settings.read_text())
        release.verify()

    def test_restart_failure_restores_original_sources(self):
        before = self.guest.read_bytes(), self.settings.read_bytes()
        calls = []
        def broken_once():
            calls.append("refresh")
            if len(calls) == 1:
                raise RuntimeError("simulated activation failure")
        with patch.object(release, "restart", broken_once):
            with self.assertRaisesRegex(RuntimeError, "simulated activation"):
                release.publish(self.stage, "42120000001")
        self.assertEqual((self.guest.read_bytes(), self.settings.read_bytes()), before)
        self.assertFalse(self.metrics.exists())
        self.assertEqual(len(calls), 2)

    def test_rejects_existing_module_without_changes(self):
        self.metrics.write_text("# preexisting")
        with self.assertRaisesRegex(RuntimeError, "METRICS_ALREADY_EXISTS"):
            release.state(self.stage)
        self.assertEqual(self.guest.read_bytes(), b"# current live guest\n")


if __name__ == "__main__":
    unittest.main()
