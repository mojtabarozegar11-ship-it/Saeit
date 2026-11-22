from io import StringIO
from unittest.mock import patch
from contextlib import contextmanager
from pathlib import Path
import os
import stat
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import SimpleTestCase


@contextmanager
def _acquired_lock():
    yield True


class EconomicAutoRunOutcomeTests(SimpleTestCase):
    @patch("core.management.commands.economic_autorun._exclusive_cycle_lock", side_effect=_acquired_lock)
    @patch("core.management.commands.economic_autorun.call_command")
    def test_idle_cycle_cannot_claim_success(self, cycle_command, lock):

        def write_command_result(name, **options):
            options["stdout"].write(
                "BRAIN_BLOCKED task=3 requires_review=true" if name == "online_income_cycle"
                else "NO_QUEUED_ECONOMIC_TASK"
            )

        cycle_command.side_effect = write_command_result
        output = StringIO()
        call_command("economic_autorun", stdout=output)
        assert "ECONOMIC_NO_TASK_EXECUTED" in output.getvalue()
        assert "ECONOMIC_INTERNAL_TASK_EXECUTED" not in output.getvalue()
        lock.assert_called_once()

    @patch("core.management.commands.economic_autorun._exclusive_cycle_lock", side_effect=_acquired_lock)
    @patch("core.management.commands.economic_autorun.call_command")
    def test_executed_task_is_not_mislabeled_collected_revenue(self, cycle_command, lock):

        def write_command_result(name, **options):
            options["stdout"].write(
                "BRAIN_DECISION action=income_market_research" if name == "online_income_cycle"
                else "EXECUTED task=23 action=income_market_research status=completed"
            )

        cycle_command.side_effect = write_command_result
        output = StringIO()
        call_command("economic_autorun", stdout=output)
        assert "ECONOMIC_INTERNAL_TASK_EXECUTED revenue_not_assessed" in output.getvalue()
        assert "ECONOMIC_CYCLE_FINISHED" not in output.getvalue()
        lock.assert_called_once()

    def test_busy_lock_does_not_plan_or_dispatch(self):
        @contextmanager
        def busy_lock():
            yield False

        with patch("core.management.commands.economic_autorun._exclusive_cycle_lock",
                   side_effect=busy_lock), patch(
                       "core.management.commands.economic_autorun.call_command"
                   ) as cycle_command:
            output = StringIO()
            call_command("economic_autorun", stdout=output)
            cycle_command.assert_not_called()
        assert "SKIP: economic cycle already running." in output.getvalue()

    def test_file_lock_is_exclusive_across_invocations_and_releases_after_exit(self):
        from core.management.commands import economic_autorun as module

        with TemporaryDirectory() as temporary, patch.object(module, "LOCK_DIR", Path(temporary)):
            with module._exclusive_cycle_lock() as first:
                assert first is True
                with module._exclusive_cycle_lock() as second:
                    assert second is False
                lock_file = Path(temporary) / module.LOCK_NAME
                assert lock_file.is_file()
                assert stat.S_IMODE(lock_file.stat().st_mode) == 0o600
            with module._exclusive_cycle_lock() as after_exit:
                assert after_exit is True

    def test_symlink_lock_target_is_rejected_without_dispatch(self):
        from django.core.management.base import CommandError
        from core.management.commands import economic_autorun as module

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "foreign-lock"
            target.touch()
            (root / module.LOCK_NAME).symlink_to(target)
            with patch.object(module, "LOCK_DIR", root):
                with self.assertRaises(CommandError):
                    with module._exclusive_cycle_lock():
                        pass
