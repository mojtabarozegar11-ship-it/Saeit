"""Local checks for the guarded capture-only release and rollback behavior."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mpw_guest_email_claim_capture_release_20261105.py"
spec = importlib.util.spec_from_file_location("mpw_capture_release", SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class TestGuardedCaptureRelease(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = self.root / "app"
        (self.app / "config").mkdir(parents=True)
        (self.app / "services").mkdir()
        self.backups = self.root / "backups"
        self.old = {
            "recovery": b"recovery old\n",
            "guest": b"guest old\n",
            "settings": b"public=False\nemail=False\n",
        }
        self.new = {
            "recovery": b"recovery new\n",
            "guest": b"guest new\n",
            "settings": b"public=False\nemail=False\ncapture=True\n",
        }
        self.original_app, self.original_backups = release.APP, release.SAFE_BACKUPS
        release.APP, release.SAFE_BACKUPS = self.app, self.backups
        self.addCleanup(self._restore_paths)
        for name, content in self.old.items():
            (self.app / release.PATHS[name]).write_bytes(content)

    def _restore_paths(self):
        release.APP, release.SAFE_BACKUPS = self.original_app, self.original_backups

    def _staged(self):
        return {key: self.new[key] for key in ("recovery", "guest")}

    def _mock_preflight(self):
        return patch.object(release, "preflight", return_value=(
            self._staged(), self.old["settings"], self.new["settings"]))

    def test_publish_writes_capture_only_and_keeps_private_originals(self):
        restarts = []
        with (self._mock_preflight(),
              patch.object(release, "db_state", return_value={"capture": True}),
              patch.object(release, "restart", side_effect=lambda: restarts.append(1)),
              patch.object(release, "verify", return_value=None)):
            release.publish(self.root / "stage", "42080431925")
        for name in self.old:
            self.assertEqual((self.app / release.PATHS[name]).read_bytes(), self.new[name])
            archived = self.backups / "42080431925" / (name + ".before")
            self.assertEqual(archived.read_bytes(), self.old[name])
            self.assertEqual(archived.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(restarts), 1)

    def test_publish_restores_all_files_if_post_release_verification_fails(self):
        restarts = []
        with (self._mock_preflight(),
              patch.object(release, "db_state", return_value={"capture": True}),
              patch.object(release, "restart", side_effect=lambda: restarts.append(1)),
              patch.object(release, "verify", side_effect=RuntimeError("bad verification"))):
            with self.assertRaisesRegex(RuntimeError, "bad verification"):
                release.publish(self.root / "stage", "42080431926")
        for name in self.old:
            self.assertEqual((self.app / release.PATHS[name]).read_bytes(), self.old[name])
        self.assertEqual(len(restarts), 2)

    def test_capture_fingerprint_and_next_one_file_upgrade_chain(self):
        self.assertEqual(release.checksum((ROOT / release.PATHS["recovery"]).read_bytes()),
                         release.AFTER["recovery"])
        next_script = ROOT / "scripts/mpw_required_email_guarded_release_20261106.py"
        spec = importlib.util.spec_from_file_location("mpw_next_email_release", next_script)
        next_release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(next_release)
        self.assertEqual(release.AFTER["guest"], next_release.BEFORE)
        self.assertEqual(next_release.digest((ROOT / release.PATHS["guest"]).read_bytes()),
                         next_release.AFTER)


if __name__ == "__main__":
    unittest.main()
