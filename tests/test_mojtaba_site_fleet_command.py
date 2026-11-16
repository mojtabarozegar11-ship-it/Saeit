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
        with patch("core.management.commands.mojtaba_site_fleet_cycle.run_one_bot_public_cycle", return_value=sample) as live:
            call_command("mojtaba_site_fleet_cycle", observe_public=True, stdout=output)
            live.assert_called_once_with()
        self.assertEqual(json.loads(output.getvalue()), sample)

    def test_wrong_bot_identity_refuses_output(self):
        from django.core.management.base import CommandError
        output = io.StringIO()
        with patch("core.management.commands.mojtaba_site_fleet_cycle.inventory",
                   return_value={"canonical_bot": "fake"}):
            with self.assertRaises(CommandError):
                call_command("mojtaba_site_fleet_cycle", stdout=output)
        self.assertEqual(output.getvalue(), "")
