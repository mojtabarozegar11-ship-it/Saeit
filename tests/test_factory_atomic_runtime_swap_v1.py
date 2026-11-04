"""Isolated failure-injection tests of the exact F-01 activation shell block.

The crontab command is replaced with an in-process test function. These tests
never contact the VPS or modify the host's real scheduler.
"""

from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/vps-single-product-factory-activation.yml"
)
MARKER = "SAEIT_SINGLE_PRODUCT_FACTORY_V1"


class AtomicRuntimeSwapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = WORKFLOW.read_text(encoding="utf-8")
        cls.transaction = textwrap.dedent(
            text.split(
                "          # Hold the lock, pause only our marked cron entry, then atomically\n",
                1,
            )[1].split(
                '          runner="$runtime/run-single-product-cycle.sh"', 1
            )[0]
        )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ops = self.root / "operations"
        self.runtime = self.ops / "single-product-runtime"
        self.next = self.ops / ".single-product-runtime.next.test"
        self.backup = self.ops / "backups" / "single-product-runtime-test"
        self.private = self.root / "private"
        self.private.mkdir()
        self.runtime.mkdir(parents=True)
        self.next.mkdir()
        self.backup.mkdir(parents=True)
        (self.runtime / "version").write_text("old")
        (self.next / "version").write_text("new")
        self.initial_cron = f"* * * * * /previous # {MARKER}\n"
        (self.backup / "crontab.before").write_text(self.initial_cron)
        self.fake_cron = self.root / "fake-crontab.txt"
        self.fake_cron.write_text(self.initial_cron)

    def run_transaction(self, injected="", fail_cron=False, no_old_runtime=False):
        if no_old_runtime:
            (self.runtime / "version").unlink()
            self.runtime.rmdir()
        shell = f"""set -euo pipefail
umask 077
ops={str(self.ops)!r}
runtime={str(self.runtime)!r}
runtime_next={str(self.next)!r}
backup={str(self.backup)!r}
private={str(self.private)!r}
stamp=test
fake_cron={str(self.fake_cron)!r}
crontab() {{
  if test "$1" = -l; then
    test -f "$fake_cron" && /bin/cat "$fake_cron"
  else
    /bin/cp "$1" "$fake_cron"
    if test "{int(fail_cron)}" = 1 && [[ "$1" == *".hold."* ]]; then
      return 67
    fi
  fi
}}
{injected}
"""
        return subprocess.run(
            ["bash", "-c", shell],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    def build(self, interruption=None):
        transaction = self.transaction
        if interruption == "after_pause":
            anchor = "test \"$(crontab -l | grep -Fc 'SAEIT_SINGLE_PRODUCT_FACTORY_V1' || true)\" -eq 0"
            self.assertIn(anchor, transaction)
            transaction = transaction.replace(anchor, anchor + "\nexit 42", 1)
        if interruption == "after_previous_move":
            self.assertIn("previous_moved=1", transaction)
            transaction = transaction.replace("previous_moved=1", "previous_moved=1\nexit 42", 1)
        ending = "exit 42" if interruption == "after_swap" else "completed=1\ntrap - EXIT"
        return transaction + "\n" + ending

    def test_success_swaps_all_files_and_preserves_previous_runtime(self):
        result = self.run_transaction(self.build())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.runtime / "version").read_text(), "new")
        self.assertEqual((self.backup / "runtime-before" / "version").read_text(), "old")
        self.assertNotIn(MARKER, self.fake_cron.read_text())

    def test_failure_after_pausing_cron_restores_old_scheduler(self):
        result = self.run_transaction(self.build("after_pause"))
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertEqual((self.runtime / "version").read_text(), "old")
        self.assertEqual(self.fake_cron.read_text(), self.initial_cron)

    def test_failure_after_old_runtime_moved_restores_it(self):
        result = self.run_transaction(self.build("after_previous_move"))
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertEqual((self.runtime / "version").read_text(), "old")
        self.assertEqual(self.fake_cron.read_text(), self.initial_cron)

    def test_failure_after_swap_reverts_and_retains_rejected_runtime(self):
        result = self.run_transaction(self.build("after_swap"))
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertEqual((self.runtime / "version").read_text(), "old")
        self.assertEqual((self.backup / "runtime-rejected" / "version").read_text(), "new")
        self.assertEqual(self.fake_cron.read_text(), self.initial_cron)

    def test_partially_failed_cron_pause_reverts_schedule(self):
        result = self.run_transaction(self.build(), fail_cron=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.runtime / "version").read_text(), "old")
        self.assertEqual(self.fake_cron.read_text(), self.initial_cron)

    def test_no_previous_runtime_rejects_candidate_without_erasing_backup(self):
        result = self.run_transaction(self.build("after_swap"), no_old_runtime=True)
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertFalse(self.runtime.exists())
        self.assertEqual((self.backup / "runtime-rejected" / "version").read_text(), "new")
        self.assertEqual(self.fake_cron.read_text(), self.initial_cron)


if __name__ == "__main__":
    unittest.main()
