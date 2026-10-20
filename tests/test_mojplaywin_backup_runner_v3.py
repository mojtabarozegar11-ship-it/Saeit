"""Pure fixture tests for the owner-only compressed-backup runner; NO SSH."""
import base64
import os
import shlex
import stat
import tempfile
import unittest
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

    def test_only_private_pinned_ssh_config_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "config"
            p.write_text(
                "Host saeit-cpanel\n ProxyJump saeit-vps\n"
                "Host *\n StrictHostKeyChecking yes\n BatchMode yes\n"
            )
            p.chmod(0o600)
            self.assertEqual(runner.checked_config(p), p)
            p.chmod(0o644)
            with self.assertRaises(ValueError):
                runner.checked_config(p)
            p.chmod(0o600)
            link = p.with_name("alias")
            link.symlink_to(p)
            with self.assertRaises(ValueError):
                runner.checked_config(link)

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
