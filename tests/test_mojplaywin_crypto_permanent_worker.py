"""No-live-money controls for the reusable MojPlayWin ETH/TRX worker."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock

from scripts.mojplaywin_crypto_permanent_worker import (
    OPERATIONS_FLAGS, RELEASE_FLAGS, ready, lock_path_is_private, one_pass,
)


class CryptoPermanentWorkerTests(TestCase):
    def test_denies_by_default_even_when_existing_apps_installed(self):
        ok, missing = ready(SimpleNamespace(), {"mpw_commerce", "mpw_native_checkout"})
        self.assertFalse(ok)
        self.assertEqual(set(missing), set(RELEASE_FLAGS + OPERATIONS_FLAGS))

    def test_all_gates_and_both_actual_apps_mandatory(self):
        flags = {x: True for x in RELEASE_FLAGS + OPERATIONS_FLAGS}
        data = SimpleNamespace(**flags)
        ok, missing = ready(data, {"mpw_commerce", "mpw_native_checkout"})
        self.assertTrue(ok)
        self.assertEqual(missing, ())
        for flag in RELEASE_FLAGS + OPERATIONS_FLAGS:
            old = flags[flag]
            flags[flag] = False
            ok, missing = ready(SimpleNamespace(**flags),
                                {"mpw_commerce", "mpw_native_checkout"})
            self.assertFalse(ok)
            self.assertIn(flag, missing)
            flags[flag] = old
        ok, missing = ready(data, {"mpw_commerce"})
        self.assertFalse(ok)
        self.assertIn("mpw_native_checkout:not_installed", missing)

    def test_lock_must_not_be_in_any_web_source_directory(self):
        with TemporaryDirectory() as tmp:
            top = Path(tmp)
            site = top / "site"
            site.mkdir()
            inner = site / "static"
            inner.mkdir()
            self.assertFalse(lock_path_is_private(site, inner / "lock"))
            self.assertFalse(lock_path_is_private(site, site / "lock"))
            self.assertFalse(lock_path_is_private(site, Path("lock")))
            private = top / "private"
            private.mkdir(mode=0o700)
            self.assertTrue(lock_path_is_private(site, private / "lock"))
            (private / "lock").symlink_to(site / "somefile")
            self.assertFalse(lock_path_is_private(site, private / "lock"))

    def test_disabled_path_never_spawns_any_command(self):
        run = MagicMock()
        outcome = one_pass(Path(__file__).resolve().parents[1],
                           Path("/nonexistent-private-dir/lock"),
                           runner=run)
        self.assertEqual(outcome, "unsafe_private_lock")
        run.assert_not_called()

    def test_one_cycle_runs_native_reconciliation_then_course_fulfillment(self):
        with TemporaryDirectory() as tmp:
            top = Path(tmp)
            site = top / "site"
            site.mkdir()
            private = top / "private"
            private.mkdir(mode=0o700)
            runner = MagicMock(return_value=SimpleNamespace(returncode=0))
            state = one_pass(site, private / "lock", runner=runner, python="/usr/bin/python3")
            self.assertEqual(state, "cycle_passed")
            self.assertEqual(runner.call_count, 2)
            self.assertEqual(runner.call_args_list[0].args[0][-1],
                             "mpw_commerce_reconcile")
            self.assertEqual(runner.call_args_list[1].args[0][-1],
                             "mpw_commerce_fulfill_courses")
            for call in runner.call_args_list:
                self.assertTrue(call.kwargs["capture_output"])
                self.assertTrue(call.kwargs["timeout"] <= 120)

    def test_failed_settlement_prevents_enrolling_unpaid_course(self):
        with TemporaryDirectory() as tmp:
            top = Path(tmp)
            site = top / "site"
            site.mkdir()
            private = top / "private"
            private.mkdir(mode=0o700)
            runner = MagicMock(return_value=SimpleNamespace(returncode=1, stderr="secret"))
            state = one_pass(site, private / "lock", runner=runner)
            self.assertEqual(state, "cycle_failed")
            runner.assert_called_once()
