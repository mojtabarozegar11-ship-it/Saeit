"""Offline tests for forwarding-only ComfyUI phone SSH authorization."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "mobile_key_authorize.py"


class KeyAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "test-home"
        self.home.mkdir()
        key = Path(self.tmp.name) / "test_ed25519"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
            check=True, capture_output=True,
        )
        self.pub = key.with_suffix(".pub").read_text()
        self.env = {**os.environ, "HOME": str(self.home)}

    def invoke(self, mode, data=""):
        return subprocess.run(
            [sys.executable, str(SCRIPT), mode],
            input=data, capture_output=True, text=True, env=self.env,
            timeout=10,
        )

    def test_authorize_status_revoke_preserve_other_keys(self):
        ssh = self.home / ".ssh"
        ssh.mkdir(mode=0o700)
        other = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA unrelated\n"
        (ssh / "authorized_keys").write_text(other)
        self.assertEqual(self.invoke("status").returncode, 0)
        for _ in range(2):
            res = self.invoke("authorize", self.pub)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        data = (ssh / "authorized_keys").read_text()
        self.assertTrue(data.startswith(other))
        self.assertEqual(data.count("saeit-comfyui-mobile-v1"), 1)
        self.assertIn('permitopen="127.0.0.1:18188"', data)
        self.assertIn('command="/bin/false"', data)
        self.assertIn("COMFYUI_MOBILE_KEY_AUTHORIZED", self.invoke("status").stdout)
        self.assertEqual(self.invoke("revoke").returncode, 0)
        self.assertEqual((ssh / "authorized_keys").read_text(), other)

    def test_reject_untrusted_key_options(self):
        attack = 'command="touch /tmp/pwned" ' + self.pub
        res = self.invoke("authorize", attack)
        self.assertNotEqual(res.returncode, 0)
        self.assertNotIn("saeit-comfyui-mobile-v1", (
            (self.home / ".ssh" / "authorized_keys").read_text()
            if (self.home / ".ssh" / "authorized_keys").exists() else ""
        ))

    def test_reject_symlinked_authorized_keys(self):
        ssh = self.home / ".ssh"
        ssh.mkdir()
        (ssh / "authorized_keys").symlink_to(Path(self.tmp.name) / "elsewhere")
        self.assertNotEqual(self.invoke("authorize", self.pub).returncode, 0)


if __name__ == "__main__":
    unittest.main()
