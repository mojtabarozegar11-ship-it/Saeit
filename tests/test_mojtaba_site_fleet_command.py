"""Canonical command tests: dispatch exactly once, no outbound network."""
import io
import json
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class CanonicalSiteFleetCommandTests(SimpleTestCase):
    def test_default_inventory_does_not_probe_sites(self):
        output = io.StringIO()
        with patch("core.management.commands.mojtaba_site_fleet_cycle.run_one_bot_public_cycle") as live:
            call_command("mojtaba_site_fleet_cycle", stdout=output)
            live.assert_not_called()
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["canonical_bot"], "mojtaba.bot.ai")
        self.assertFalse(payload["legacy_cleanup_authorized"])

    def test_explicit_public_observation_only_once(self):
        output = io.StringIO()
        sample = {"canonical_bot": "mojtaba.bot.ai",
                  "public_checks_count": 14, "payments_collected": 0}
        with patch("core.management.commands.mojtaba_site_fleet_cycle.Agent.objects.filter") as rows, \
             patch("core.management.commands.mojtaba_site_fleet_cycle.run_one_bot_public_cycle", return_value=sample) as live:
            rows.return_value.count.return_value = 1
            call_command("mojtaba_site_fleet_cycle", observe_public=True, stdout=output)
            rows.assert_called_once_with(code="mojtaba-bot-ai", active=True)
            live.assert_called_once_with()
        self.assertEqual(json.loads(output.getvalue()), sample)

    def test_missing_canonical_agent_blocks_execution(self):
        from django.core.management.base import CommandError
        output = io.StringIO()
        with patch("core.management.commands.mojtaba_site_fleet_cycle.Agent.objects.filter") as rows, \
             patch("core.management.commands.mojtaba_site_fleet_cycle.run_one_bot_public_cycle") as live:
            rows.return_value.count.return_value = 0
            with self.assertRaises(CommandError):
                call_command("mojtaba_site_fleet_cycle", observe_public=True, stdout=output)
            live.assert_not_called()
        self.assertEqual(output.getvalue(), "")

    def test_record_requires_live_observation(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command("mojtaba_site_fleet_cycle", record_receipt=True)

    def test_explicit_record_uses_bounded_audit_adapter(self):
        output = io.StringIO()
        sample = {"canonical_bot": "mojtaba.bot.ai", "public_checks_count": 14}
        with patch("core.management.commands.mojtaba_site_fleet_cycle.Agent.objects.filter") as rows, \
             patch("core.management.commands.mojtaba_site_fleet_cycle.run_one_bot_public_cycle", return_value=sample) as live, \
             patch("core.management.commands.mojtaba_site_fleet_cycle.record_public_cycle", return_value={"written": True}) as ledger:
            rows.return_value.count.return_value = 1
            call_command("mojtaba_site_fleet_cycle", observe_public=True,
                         record_receipt=True, stdout=output)
            live.assert_called_once_with()
            ledger.assert_called_once()
            self.assertEqual(ledger.call_args.args[0], sample)
            self.assertEqual(len(ledger.call_args.kwargs["cycle_id"]), 32)
        self.assertTrue(json.loads(output.getvalue())["durable_receipt"]["written"])

    def test_private_collection_requires_explicit_recorded_public_cycle(self):
        from django.core.management.base import CommandError
        with patch("core.management.commands.mojtaba_site_fleet_cycle.collect_private_mpw_as_canonical_bot") as collector:
            with self.assertRaises(CommandError):
                call_command("mojtaba_site_fleet_cycle", collect_private_mpw=True)
            collector.assert_not_called()

    def test_legacy_private_worker_is_invoked_only_after_explicit_receipt(self):
        output = io.StringIO()
        sample = {"canonical_bot": "mojtaba.bot.ai", "public_checks_count": 14}
        with patch("core.management.commands.mojtaba_site_fleet_cycle.Agent.objects.filter") as agent, \
             patch("core.management.commands.mojtaba_site_fleet_cycle.run_one_bot_public_cycle", return_value=sample), \
             patch("core.management.commands.mojtaba_site_fleet_cycle.record_public_cycle", return_value={"written": True}), \
             patch("core.management.commands.mojtaba_site_fleet_cycle.collect_private_mpw_as_canonical_bot", return_value={"tenant": "mojplaywin"}) as collector:
            agent.return_value.count.return_value = 1
            call_command("mojtaba_site_fleet_cycle", observe_public=True,
                         record_receipt=True, collect_private_mpw=True,
                         stdout=output)
            collector.assert_called_once_with()
        self.assertEqual(json.loads(output.getvalue())["private_mpw_history"]["tenant"], "mojplaywin")

    def test_wrong_bot_identity_refuses_output(self):
        from django.core.management.base import CommandError
        output = io.StringIO()
        with patch("core.management.commands.mojtaba_site_fleet_cycle.inventory",
                   return_value={"canonical_bot": "fake"}):
            with self.assertRaises(CommandError):
                call_command("mojtaba_site_fleet_cycle", stdout=output)
        self.assertEqual(output.getvalue(), "")
