"""Contract tests for the one-file, exact-base MojPlayWin 404 release gate."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mpw_guest_checkout_live_release.py"
SPEC = importlib.util.spec_from_file_location("mpw_onefile_release_controller", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)

KNOWN_OLD = "7693254e4ed72141b6de7fc283c5a3214159ea49d838318337e47e86953f5f2f"


class OneFileReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.guest = Path(self.directory.name) / "guest.py"
        self.guest.write_bytes(b"old")
        self.old = {"pages": b"public unchanged", "web": b"commercial unchanged"}

    def exercise(self, *, guest_bytes=b"old", changes=None, needed=True):
        if guest_bytes is None:
            self.guest.unlink()
        else:
            self.guest.write_bytes(guest_bytes)
        after = dict(self.old)
        after.update(changes or {})
        with (
            mock.patch.object(release, "guard"),
            mock.patch.object(release, "TARGETS", {"guest": self.guest}),
            mock.patch.object(release, "source_from", return_value=b"reviewed candidate"),
            mock.patch.object(release, "plan", return_value=(self.old, after, needed)),
            mock.patch.object(release, "digest",
                              side_effect=lambda data: KNOWN_OLD if data == b"old" else "wrong"),
            mock.patch.object(release, "publish") as publish,
        ):
            release.publish_onefile("41397000000", "candidate.py")
            publish.assert_called_once_with("41397000000", "candidate.py")

    def test_exact_old_sha_unchanged_hooks_allows_only_one_file(self):
        self.exercise()

    def test_unknown_existing_guest_base_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "ONE_FILE_EXACT_OLD_SHA_REQUIRED"):
            self.exercise(guest_bytes=b"unknown")

    def test_guest_missing_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "ONE_FILE_EXACT_OLD_SHA_REQUIRED"):
            self.exercise(guest_bytes=None)

    def test_public_pages_change_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "ONE_FILE_ONLY_PLAN_REQUIRED"):
            self.exercise(changes={"pages": b"altered"})

    def test_commercial_web_change_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "ONE_FILE_ONLY_PLAN_REQUIRED"):
            self.exercise(changes={"web": b"altered"})

    def test_idempotent_or_not_needed_plan_does_not_publish(self):
        with self.assertRaisesRegex(RuntimeError, "ONE_FILE_ONLY_PLAN_REQUIRED"):
            self.exercise(needed=False)



class PassengerRestartRootTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = Path(self.directory.name) / "Saeit-staging"
        self.public = Path(self.directory.name) / "mojplaywin.com"
        (self.app / "services").mkdir(parents=True)
        (self.app / "tmp").mkdir()
        (self.public / "tmp").mkdir(parents=True)
        (self.public / "passenger_wsgi.py").write_text(
            "APP='/home/zomorod2/Saeit-staging'" + chr(10), encoding="utf8")
        (self.public / ".htaccess").write_text(
            "PassengerAppRoot " + str(self.public) + chr(10), encoding="utf8")
        self.pages = self.app / "services/mpw_trx_public_pages.py"
        self.web = self.app / "services/mpw_trx_commercial_web.py"
        self.pages.write_text("# safe", encoding="utf8")
        self.web.write_text("# safe", encoding="utf8")

    def guard(self):
        with (
            mock.patch.object(release, "APP", self.app),
            mock.patch.object(release, "PUBLIC", self.public),
            mock.patch.object(release, "TARGETS", {"pages": self.pages, "web": self.web}),
            mock.patch.object(release.pwd, "getpwuid", return_value=mock.Mock(pw_name="zomorod2")),
        ):
            release.guard()

    def test_guard_accepts_matching_registered_public_root(self):
        self.guard()

    def test_guard_rejects_app_root_drift(self):
        (self.public / ".htaccess").write_text(
            "PassengerAppRoot " + str(self.app) + chr(10), encoding="utf8")
        with self.assertRaisesRegex(RuntimeError, "PASSENGER_REGISTERED_ROOT_MISMATCH"):
            self.guard()

    def test_restart_touches_actual_public_passenger_root(self):
        with mock.patch.object(release, "PUBLIC", self.public):
            release.restart()
        self.assertTrue((self.public / "tmp/restart.txt").is_file())
        self.assertFalse((self.app / "tmp/restart.txt").exists())

    def test_restart_rejects_symlink_marker(self):
        target = self.app / "tmp/restart.txt"
        target.write_text("unchanged", encoding="utf8")
        (self.public / "tmp/restart.txt").symlink_to(target)
        with mock.patch.object(release, "PUBLIC", self.public):
            with self.assertRaisesRegex(RuntimeError, "UNSAFE_PASSENGER_RESTART_MARKER"):
                release.restart()
        self.assertEqual(target.read_text(encoding="utf8"), "unchanged")


if __name__ == "__main__":
    unittest.main()
