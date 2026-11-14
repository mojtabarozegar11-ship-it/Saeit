"""Offline regression for the pinned, read-only cPanel transport.

Run from Saeit root: python3 -m unittest discover -s tests
-p 'test_mpw_cpanel_direct_first_transport_readonly.py'
No server, SSH session, secret or customer data is contacted.
"""
import os
import pathlib
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts import mpw_cpanel_direct_first_transport_readonly as m


class DirectFirstTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = pathlib.Path(self.tmp.name)

    def mock_successful_keys(self):
        return patch.object(m, "_key", return_value=None)

    def test_01_pinned_cpanel_identity_constant(self):
        self.assertTrue(m.CPANEL_EDPIN.startswith("SHA256:"))
        self.assertEqual(m.CPANEL_PORT, "1396")

    def test_02_pinned_vps_identity_constant(self):
        self.assertTrue(m.VPS_RSAPIN.startswith("SHA256:"))
        self.assertNotEqual(m.CPANEL_EDPIN, m.VPS_RSAPIN)

    def test_03_no_overwrite_existing_key_material(self):
        path = self.home / "private.key"
        m._write_private(path, "old")
        with self.assertRaises(FileExistsError):
            m._write_private(path, "new")
        self.assertEqual(path.read_text(), "old")

    def test_04_private_permissions(self):
        path = self.home / "private.key"
        m._write_private(path, "only-test")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_05_empty_key_is_rejected(self):
        with self.assertRaises(ValueError):
            m._key("  ", self.home / "empty.key")

    def test_06_key_crlf_normalization(self):
        p = self.home / "key"
        with patch.object(m, "_run", return_value=types.SimpleNamespace(returncode=0)):
            m._key("line1\r\nline2\r\n", p)
        self.assertEqual(p.read_text(), "line1\nline2\n")

    def test_07_pin_mismatch_fails_closed(self):
        path = self.home / "known"
        reply = types.SimpleNamespace(returncode=0, stdout="256 SHA256:OTHER cpanel (ED25519)\n")
        with patch.object(m, "_run", return_value=reply):
            with self.assertRaises(m.HostIdentityChanged):
                m._pin_scanned("host ssh-ed25519 aaa", path, m.CPANEL_EDPIN)

    def test_08_pinned_exact_match_accepted(self):
        path = self.home / "known"
        reply = types.SimpleNamespace(returncode=0, stdout="256 " + m.CPANEL_EDPIN + " host (ED25519)\n")
        with patch.object(m, "_run", return_value=reply):
            self.assertTrue(m._pin_scanned("host ssh-ed25519 aaa", path, m.CPANEL_EDPIN))

    def test_09_missing_scan_is_not_accepted(self):
        self.assertFalse(m._pin_scanned("", self.home / "known", m.CPANEL_EDPIN))

    def test_10_malformed_pin_output_denied(self):
        with patch.object(m, "_run", return_value=types.SimpleNamespace(returncode=0, stdout="bad\n")):
            self.assertFalse(m._pin_scanned("host key", self.home / "known", m.CPANEL_EDPIN))

    def test_11_direct_config_has_no_proxy(self):
        path = self.home / "config"
        m._config(path, self.home, via_vps=False)
        s = path.read_text()
        self.assertNotIn("ProxyJump saeit-vps", s)
        self.assertIn("StrictHostKeyChecking yes", s)
        self.assertIn("ForwardAgent no", s)

    def test_12_fallback_config_has_pinned_proxy(self):
        path = self.home / "config"
        m._config(path, self.home, via_vps=True)
        s = path.read_text()
        self.assertIn("ProxyJump saeit-vps", s)
        self.assertIn("UserKnownHostsFile ", s)
        self.assertIn("IdentityFile ", s)

    def test_13_connection_success_must_be_exact_cpanel_user(self):
        with patch.object(m, "_run", return_value=types.SimpleNamespace(returncode=0, stdout="other\n")):
            self.assertFalse(m._cpanel_identity(self.home / "config"))

    def test_14_connection_success_when_exact_user(self):
        with patch.object(m, "_run", return_value=types.SimpleNamespace(returncode=0, stdout="zomorod2\n")):
            self.assertTrue(m._cpanel_identity(self.home / "config"))

    def test_15_direct_route_precedes_vps_probe(self):
        with patch.dict(os.environ, {"RUNNER_TEMP": str(self.home), "HOST_KEY": "mock",
                                     "VPS_KEY": "mock"}):
            with self.mock_successful_keys(), patch.object(m, "_scan", return_value=True) as scans:
                with patch.object(m, "_cpanel_identity", return_value=True):
                    self.assertEqual(m.main(), 0)
                    self.assertEqual(scans.call_count, 1)
                    self.assertEqual(scans.call_args.args[0], m.CPANEL_HOST)

    def test_16_vps_is_fallback_only(self):
        with patch.dict(os.environ, {"RUNNER_TEMP": str(self.home), "HOST_KEY": "mock",
                                     "VPS_KEY": "mock"}):
            with self.mock_successful_keys(), patch.object(m, "_scan", side_effect=[False, True, True]) as scans:
                with patch.object(m, "_cpanel_identity", return_value=True):
                    self.assertEqual(m.main(), 0)
                    self.assertEqual(scans.call_count, 3)
                    self.assertEqual(scans.call_args_list[1].args[0], m.VPS_ADDR)

    def test_17_both_routes_unreachable_refuse(self):
        with patch.dict(os.environ, {"RUNNER_TEMP": str(self.home), "HOST_KEY": "mock",
                                     "VPS_KEY": "mock"}):
            with self.mock_successful_keys(), patch.object(m, "_scan", side_effect=[False, False]):
                self.assertEqual(m.main(), 2)

    def test_18_wrong_pin_must_not_fallback(self):
        with patch.dict(os.environ, {"RUNNER_TEMP": str(self.home), "HOST_KEY": "mock",
                                     "VPS_KEY": "mock"}):
            with self.mock_successful_keys(), patch.object(m, "_scan",
                    side_effect=m.HostIdentityChanged("pin mismatch")) as scans:
                with self.assertRaises(m.HostIdentityChanged):
                    m.main()
                self.assertEqual(scans.call_count, 1)

    def test_19_no_runner_temp_denied(self):
        with patch.dict(os.environ, {"RUNNER_TEMP": "", "HOST_KEY": "mock",
                                     "VPS_KEY": "mock"}):
            with self.assertRaises(ValueError):
                m.main()

    def test_20_bounded_scan_retries(self):
        with patch.object(m, "_run", return_value=None) as calls:
            self.assertFalse(m._scan(m.VPS_ADDR, "22", "rsa",
                                     self.home / "known", m.VPS_RSAPIN))
        self.assertEqual(calls.call_count, m.MAX_ATTEMPTS)

    def test_21_cpanel_identity_requires_success_exit(self):
        with patch.object(m, "_run", return_value=types.SimpleNamespace(returncode=255, stdout="zomorod2")):
            self.assertFalse(m._cpanel_identity(self.home / "config"))

    def test_22_direct_auth_failure_can_retry_pinned_vps(self):
        with patch.dict(os.environ, {"RUNNER_TEMP": str(self.home), "HOST_KEY": "mock",
                                     "VPS_KEY": "mock"}):
            with self.mock_successful_keys(), patch.object(m, "_scan", return_value=True) as scans:
                with patch.object(m, "_cpanel_identity", side_effect=[False, True]):
                    self.assertEqual(m.main(), 0)
                    self.assertEqual(scans.call_count, 3)

    def test_23_no_unsafe_host_key_bypass(self):
        config = self.home / "config"
        m._config(config, self.home, via_vps=True)
        s = config.read_text()
        self.assertNotIn("StrictHostKeyChecking no", s)
        self.assertNotIn("UserKnownHostsFile /dev/null", s)
        self.assertNotIn("ForwardAgent yes", s)

    def test_24_no_password_prompt_in_config(self):
        config = self.home / "config"
        m._config(config, self.home, via_vps=False)
        self.assertIn("BatchMode yes", config.read_text())
        self.assertIn("RequestTTY no", config.read_text())


if __name__ == "__main__":
    unittest.main()
