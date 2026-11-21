"""Dependency-free proof of the actual host-wide master-cycle file lock.

Extract its implementation from Django command source; neither Django nor the
production database, cron, cache or VPS are touched by this suite.
"""

import ast
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "core" / "management" /
          "commands" / "economic_autorun.py")


def _lock_function(directory):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "_exclusive_cycle_lock"]
    assert len(selected) == 1
    environment = {
        "contextmanager": contextmanager,
        "fcntl": fcntl,
        "os": os,
        "Path": Path,
        "stat": stat,
        "CommandError": RuntimeError,
        "LOCK_DIR": Path(directory),
        "LOCK_NAME": "economic-autorun.lock",
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), environment)
    return environment["_exclusive_cycle_lock"]


class EconomicCycleLockContractTest(unittest.TestCase):
    def test_contending_entry_is_rejected_and_next_entry_succeeds(self):
        with TemporaryDirectory() as directory:
            acquire = _lock_function(directory)
            with acquire() as first:
                self.assertTrue(first)
                with acquire() as second:
                    self.assertFalse(second)
            with acquire() as third:
                self.assertTrue(third)

    def test_lock_file_is_private_regular_file(self):
        with TemporaryDirectory() as directory:
            acquire = _lock_function(directory)
            with acquire() as held:
                self.assertTrue(held)
                path = Path(directory) / "economic-autorun.lock"
                self.assertTrue(path.is_file())
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_separate_python_process_cannot_take_held_lock(self):
        script = (
            "import fcntl, os, sys; "
            "fd=os.open(sys.argv[1], os.O_RDWR); "
            "\ntry: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)"
            "\nexcept BlockingIOError: sys.exit(2)"
            "\nsys.exit(0)"
        )
        with TemporaryDirectory() as directory:
            acquire = _lock_function(directory)
            path = Path(directory) / "economic-autorun.lock"
            with acquire() as held:
                self.assertTrue(held)
                blocked = subprocess.run(
                    [sys.executable, "-c", script, str(path)],
                    check=False, capture_output=True, timeout=5,
                )
                self.assertEqual(blocked.returncode, 2, blocked.stderr)
            released = subprocess.run(
                [sys.executable, "-c", script, str(path)],
                check=False, capture_output=True, timeout=5,
            )
            self.assertEqual(released.returncode, 0, released.stderr)

    def test_symlink_and_world_writable_directory_fail_closed(self):
        with TemporaryDirectory() as directory:
            base = Path(directory)
            victim = base / "not-the-lock"
            victim.touch()
            (base / "economic-autorun.lock").symlink_to(victim)
            acquire = _lock_function(base)
            with self.assertRaisesRegex(RuntimeError, "ECONOMIC_CYCLE_LOCK_UNAVAILABLE"):
                with acquire():
                    self.fail("A symlink must not be locked")
        with TemporaryDirectory() as directory:
            base = Path(directory)
            os.chmod(base, 0o777)
            acquire = _lock_function(base)
            with self.assertRaisesRegex(RuntimeError, "ECONOMIC_CYCLE_LOCK_UNAVAILABLE"):
                with acquire():
                    self.fail("A writable-by-others directory must not be trusted")


if __name__ == "__main__":
    unittest.main()
