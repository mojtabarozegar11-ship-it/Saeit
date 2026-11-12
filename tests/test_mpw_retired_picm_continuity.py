"""Offline regression: retired PICM must be absent, not mistaken for a live outage."""

from __future__ import annotations

import importlib.util
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mpw_subsite_continuity_guard_20261026.py"
SPEC = importlib.util.spec_from_file_location("mpw_retired_picm_guard", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = guard
SPEC.loader.exec_module(guard)


class RetiredPicmContinuityTests(unittest.TestCase):
    def test_retired_picm_is_not_a_live_child(self):
        self.assertNotIn("/picm/", guard.REQUIRED_PATHS)
        self.assertNotIn("/picm/", guard.PROTECTED_CHILDREN)
        self.assertEqual(guard.RETIRED_PATHS, ("/picm/",))
        self.assertNotIn("/picm/login/", guard.REDIRECT_PATHS)
        self.assertIn("/zahra$$/", guard.REQUIRED_PATHS)

    def test_exact_404_passes_retirement_gate(self):
        url = guard.ORIGIN + "/picm/"
        with mock.patch.object(guard, "get", return_value=(guard.Check(url, url, 404, 0), b"")):
            self.assertEqual(guard.check_retired_picm().status, 404)

    def test_active_picm_or_redirect_fails_retirement_gate(self):
        url = guard.ORIGIN + "/picm/"
        for status, effective in ((200, url), (302, url), (404, guard.ORIGIN + "/picm/login/")):
            with self.subTest(status=status, effective=effective):
                with mock.patch.object(guard, "get", return_value=(guard.Check(url, effective, status, 0), b"")):
                    with self.assertRaises(RuntimeError):
                        guard.check_retired_picm()

    def test_404_exception_allowed_only_for_explicit_retirement(self):
        class MissingPageOpener:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

        url = guard.ORIGIN + "/picm/"
        with mock.patch.object(guard.urllib.request, "build_opener", return_value=MissingPageOpener()):
            check, _ = guard.get(url, attempts=1, allow_retired_404=True)
            self.assertEqual(check.status, 404)
            for other, allow in ((url, False), (guard.ORIGIN + "/farnaz/", True)):
                with self.subTest(url=other, allow=allow):
                    with self.assertRaises(RuntimeError):
                        guard.get(other, attempts=1, allow_retired_404=allow)

    def test_untrusted_direct_redirect_still_denied(self):
        self.assertFalse(guard._approved_direct_get("http://mojplaywin.com/picm/"))
        self.assertFalse(guard._approved_direct_get("https://example.com/picm/"))
        self.assertFalse(guard._approved_direct_get(guard.ORIGIN + "/picm/login/"))
        self.assertTrue(guard._approved_direct_get(guard.ORIGIN + "/picm/"))


if __name__ == "__main__":
    unittest.main()
