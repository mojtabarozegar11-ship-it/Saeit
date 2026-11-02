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


if __name__ == "__main__":
    unittest.main()
