#!/usr/bin/env python3
"""Offline quota contract tests. All UAPI output is synthetic; no live cPanel IO."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts/zomorod_business_genetics_readonly_preflight.sh"
INSTALLER = ROOT / "scripts/zomorod_business_genetics_guarded_install.sh"


def extract_quota_python(path: Path):
    source = path.read_text(encoding="utf-8")
    found = re.findall(r"python3 - \"\$db_bytes\" <<'PY_QUOTA'\n(.*?)\nPY_QUOTA", source, re.S)
    if len(found) != 1:
        raise AssertionError("Expected exactly one fail-closed quota gate in " + path.name)
    return found[0]


def check_quota_gate(script: str, payload, return_code=0):
    with tempfile.TemporaryDirectory(prefix="zm-quota-fixture-") as name:
        bin_path = Path(name) / "uapi"
        # The only executable called by the quota gate is this local fake UAPI.
        if payload is None:
            bin_path.write_text("#!/bin/sh\nprintf '%s' 'invalid-json'\n", encoding="utf-8")
        else:
            data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
            bin_path.write_text("#!/bin/sh\nprintf '%s' '" + data + "'\nexit " + str(return_code) + "\n", encoding="utf-8")
        bin_path.chmod(0o700)
        env = dict(os.environ, PATH=name + os.pathsep + os.environ.get("PATH", ""))
        return subprocess.run(
            [sys.executable, "-c", script, "348160"],
            capture_output=True, text=True, env=env, timeout=6, check=False,
        )


class BusinessQuotaGuard(unittest.TestCase):
    def test_both_guards_allow_verified_headroom(self):
        payload = {"result": {"status": 1, "data": {
            "byte_limit": 4_000_000_000, "bytes_used": 1_000_000_000,
        }}}
        for path in (PREFLIGHT, INSTALLER):
            with self.subTest(script=path.name):
                result = check_quota_gate(extract_quota_python(path), payload)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("_CPANEL_QUOTA=VERIFIED_ENOUGH", result.stdout)

    def test_both_guards_fail_closed_on_low_quota(self):
        payload = {"result": {"status": 1, "data": {
            "byte_limit": 105_000_000, "bytes_used": 5_000_000,
        }}}
        for path in (PREFLIGHT, INSTALLER):
            with self.subTest(script=path.name):
                result = check_quota_gate(extract_quota_python(path), payload)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("_CPANEL_QUOTA=INSUFFICIENT", result.stdout)

    def test_both_guards_reject_unverified_quota(self):
        bad_payloads = [
            None,
            {"result": {"status": 0, "data": {"byte_limit": 9_000_000_000, "bytes_used": 0}}},
            {"result": {"status": 1, "data": {"byte_limit": "unlimited", "bytes_used": 0}}},
            {"result": {"status": 1, "data": {"byte_limit": -5, "bytes_used": 0}}},
            {"result": {"status": 1, "data": {"byte_limit": 1000, "bytes_used": 2000}}},
            {"result": {"status": 1, "data": []}},
        ]
        for path in (PREFLIGHT, INSTALLER):
            script = extract_quota_python(path)
            for payload in bad_payloads:
                with self.subTest(script=path.name, payload=payload):
                    result = check_quota_gate(script, payload)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("_CPANEL_QUOTA=UNVERIFIED", result.stdout)

    def test_both_guards_refuse_bad_uapi_exit_code(self):
        payload = {"result": {"status": 1, "data": {
            "byte_limit": 4_000_000_000, "bytes_used": 1_000_000_000,
        }}}
        for path in (PREFLIGHT, INSTALLER):
            with self.subTest(script=path.name):
                result = check_quota_gate(extract_quota_python(path), payload, return_code=1)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("_CPANEL_QUOTA=UNVERIFIED", result.stdout)


if __name__ == "__main__":
    unittest.main()
