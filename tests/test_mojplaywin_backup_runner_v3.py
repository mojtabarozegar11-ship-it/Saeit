"""Pure fixture tests for the owner-only compressed-backup runner; NO SSH."""
import base64
import os
import shlex
import stat
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from scripts import mojplaywin_backup_gzip_runner_v3 as runner


class RunnerContract(unittest.TestCase):
    def test_commands_are_shell_escaped_and_scoped(self):
        encoded = base64.b64encode(b"harmless test source").decode("ascii")
        src = shlex.split(runner.remote_command(encoded, "mysql"))
        self.assertEqual(src[:2], ["python3", "-c"])
        self.assertEqual(src[-2:], [encoded, "mysql"])
        dst = shlex.split(runner.remote_command(encoded, "files", stem="mojplaywin_20261020"))
        self.assertEqual(dst[:2], ["python3", "-c"])
        self.assertEqual(dst[-3:], [encoded, "files", "mojplaywin_20261020"])
        with self.assertRaises(ValueError):
            runner.remote_command(encoded, "mysql;echo bad", stem="mojplaywin_20261020")
        with self.assertRaises(ValueError):
            runner.remote_command(encoded, "mysql", stem="../forbidden")

    def test_only_private_exactly_host_pinned_ssh_config_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            d = Path(folder)
            for name in ("vps.key", "vps.known", "host.key", "host.known"):
                item = d / name
                item.write_text("synthetic fixture")
                item.chmod(0o600)
            p = d / "config"
            good = (
                "Host saeit-vps\n"
                " HostName 178.239.147.150\n User githubops\n Port 22\n"
                f" IdentityFile {d}/vps.key\n UserKnownHostsFile {d}/vps.known\n"
                "Host saeit-cpanel\n"
                " HostName zohal.pws-dns.net\n User zomorod2\n Port 1396\n"
                f" IdentityFile {d}/host.key\n UserKnownHostsFile {d}/host.known\n"
                " ProxyJump saeit-vps\n"
                "Host *\n StrictHostKeyChecking yes\n IdentitiesOnly yes\n"
                " BatchMode yes\n ConnectTimeout 10\n ConnectionAttempts 1\n"
                " ForwardAgent no\n RequestTTY no\n"
            )
            p.write_text(good)
            p.chmod(0o600)
            pins = {
                "vps.known": runner.EXPECTED_HOSTS["saeit-vps"]["fingerprint"],
                "host.known": runner.EXPECTED_HOSTS["saeit-cpanel"]["fingerprint"],
            }
            def fake_ssh_keygen(command, **kw):
                self.assertEqual(command[:2], ["ssh-keygen", "-lf"])
                pin = pins[Path(command[2]).name]
                return SimpleNamespace(returncode=0, stdout=f"256 {pin} verified-fixture (ED25519)\n")
            with patch.object(runner.subprocess, "run", side_effect=fake_ssh_keygen):
                self.assertEqual(runner.checked_config(p), p)
                for bad in (
                    good.replace("HostName 178.239.147.150", "HostName attacker.invalid"),
                    good.replace("User zomorod2", "User root"),
                    good.replace("StrictHostKeyChecking yes", "StrictHostKeyChecking accept-new"),
                    good.replace("ForwardAgent no", "ForwardAgent yes"),
                    good + "Match exec true\n",
                    good + "Include /tmp/ssh-override\n",
                    good + "ProxyCommand sh -c evil\n",
                ):
                    p.write_text(bad)
                    with self.assertRaises(ValueError):
                        runner.checked_config(p)
                p.write_text(good)
                p.chmod(0o644)
                with self.assertRaises(ValueError):
                    runner.checked_config(p)
                p.chmod(0o600)
                with patch.object(runner.subprocess, "run",
                                  return_value=SimpleNamespace(returncode=0, stdout="256 SHA256:fake fixture\n")):
                    with self.assertRaises(ValueError):
                        runner.checked_config(p)
                alias = p.with_name("alias")
                alias.symlink_to(p)
                with self.assertRaises(ValueError):
                    runner.checked_config(alias)

    def test_source_code_is_bounded_and_named(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / runner.EXPECTED_SOURCE.rsplit("/", 1)[-1]
            p.write_bytes(b"test" * 400)
            self.assertEqual(base64.b64decode(runner.script_bytes(p, p.name)), p.read_bytes())
            with self.assertRaises(ValueError):
                runner.script_bytes(p, "wrong_name.py")

    def test_time_and_publication_guards(self):
        with self.assertRaises(ValueError):
            runner.transfer("ignored", "abc", "def", "mysql", stem="mojplaywin_20261020", timeout=999999)


if __name__ == "__main__":
    unittest.main()
