import fcntl
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from termux_bridge.autostart import (
    SIGNATURE, boot_script, install, is_locked, paths,
    run_forever, start,
)
from termux_bridge.worker import BridgeError


def phone_sandbox(home):
    state, checkout, script = paths(home)
    (checkout / "termux_bridge").mkdir(parents=True)
    (checkout / "bridge").mkdir(parents=True)
    (checkout / "termux_bridge" / "worker.py").write_text("pass\n")
    (checkout / "termux_bridge" / "autostart.py").write_text("pass\n")
    (checkout / "bridge" / "command.json").write_text("{}\n")
    return state, checkout, script


class FakeBridge:
    def __init__(self, responses=None):
        self.calls = 0
        self.responses = responses or ["ALREADY_HANDLED"]

    def once(self):
        i = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        value = self.responses[i]
        if isinstance(value, Exception):
            raise value
        return value


class TermuxBootTests(unittest.TestCase):
    def test_boot_install_creates_only_private_hook(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            state, checkout, script = phone_sandbox(home)
            self.assertEqual(install(home, check_termux=False), "BOOT_HOOK_INSTALLED")
            self.assertEqual(script.read_text(), boot_script())
            self.assertIn(SIGNATURE, script.read_text())
            self.assertEqual(script.stat().st_mode & 0o777, 0o700)
            self.assertEqual(script.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(install(home, check_termux=False), "BOOT_HOOK_ALREADY_INSTALLED")
            self.assertNotIn("0.0.0.0", script.read_text())
            self.assertNotIn("sudo", script.read_text())

    def test_install_refuses_to_overwrite_user_boot_file(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            _, _, script = phone_sandbox(home)
            script.parent.mkdir(parents=True)
            script.write_text("#!/bin/sh\necho unrelated\n")
            with self.assertRaisesRegex(BridgeError, "another boot launcher"):
                install(home, check_termux=False)
            self.assertIn("unrelated", script.read_text())

    def test_install_refuses_symlink_script(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            _, _, script = phone_sandbox(home)
            script.parent.mkdir(parents=True)
            foreign = home / "foreign"
            foreign.write_text("precious\n")
            script.symlink_to(foreign)
            with self.assertRaisesRegex(BridgeError, "symlink"):
                install(home, check_termux=False)
            self.assertEqual(foreign.read_text(), "precious\n")

    def test_worker_single_instance_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            state, _, _ = phone_sandbox(home)
            state.mkdir(parents=True, exist_ok=True)
            lockpath = state / "autostart.lock"
            with lockpath.open("a+") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertTrue(is_locked(lockpath))
                worker = FakeBridge()
                self.assertEqual(
                    run_forever(home, limit=1, bridge=worker),
                    0,
                )
                self.assertEqual(worker.calls, 0)
            self.assertFalse(is_locked(lockpath))

    def test_loop_interval_and_error_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            state, _, _ = phone_sandbox(home)
            worker = FakeBridge([BridgeError("git operation failed"), "ALREADY_HANDLED", "SAFE_COMMAND_RECEIPT_PUSHED"])
            sleeps = []
            self.assertEqual(
                run_forever(home, interval=300, bridge=worker,
                            snooze=sleeps.append, limit=3),
                0,
            )
            self.assertEqual(worker.calls, 3)
            self.assertEqual(sleeps, [300, 300])

    def test_start_spawns_only_dedicated_module_not_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            state, checkout, _ = phone_sandbox(home)
            spawned = []
            def fake_popen(args, **kwargs):
                spawned.append((args, kwargs))
                return Mock(pid=101)
            result = start(home, python="python-test", spawner=fake_popen)
            self.assertEqual(result, "SAEIT_BACKGROUND_WORKER_LAUNCHED")
            self.assertEqual(len(spawned), 1)
            args, kwargs = spawned[0]
            self.assertEqual(args, [
                "python-test", "-m", "termux_bridge.autostart", "--run",
            ])
            self.assertEqual(kwargs["cwd"], str(checkout))
            self.assertTrue(kwargs["start_new_session"])
            self.assertTrue(kwargs["close_fds"])

    def test_missing_source_blocks_install(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            with self.assertRaisesRegex(BridgeError, "checkout missing"):
                install(home, check_termux=False)


if __name__ == "__main__":
    unittest.main()
