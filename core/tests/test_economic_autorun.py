from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class EconomicAutoRunOutcomeTests(SimpleTestCase):
    @patch("core.management.commands.economic_autorun.cache")
    @patch("core.management.commands.economic_autorun.call_command")
    def test_idle_cycle_cannot_claim_success(self, cycle_command, cache):
        cache.add.return_value = True

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
        cache.delete.assert_called_once()

    @patch("core.management.commands.economic_autorun.cache")
    @patch("core.management.commands.economic_autorun.call_command")
    def test_executed_task_is_not_mislabeled_collected_revenue(self, cycle_command, cache):
        cache.add.return_value = True

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
        cache.delete.assert_called_once()
