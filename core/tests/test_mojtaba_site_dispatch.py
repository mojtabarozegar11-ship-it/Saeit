import io
import json
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from core.models import Agent, AuditLog
from core.mojtaba_site_dispatch import CLAIM, execute_site_cycle
from core.mojtaba_site_fleet import SiteFleetError
from core.mojtaba_site_receipts import ACTION

class CanonicalSiteDispatchTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(code="mojtaba-bot-ai",
            name="Mojtaba.bot.ai", mission="Canonical site capability", active=True)
        self.urls = []

    def transport(self, url):
        self.urls.append(url)
        self.assertTrue(AuditLog.objects.filter(action=CLAIM).exists())
        return 200, "text/html", b"<html><head><title>site</title></head><body><h1>Sample</h1></body></html>"

    def test_claim_precedes_network_and_records_two_tenants(self):
        report = execute_site_cycle("a"*32, transport=self.transport)
        self.assertEqual(len(self.urls), 14)
        self.assertEqual(report["site_receipts"], 2)
        self.assertEqual(AuditLog.objects.filter(action=ACTION).count(), 2)
        self.assertFalse(report["legacy_retirement_authorized"])

    def test_replay_across_new_hubs_never_repeats_network(self):
        execute_site_cycle("b"*32, transport=self.transport)
        with self.assertRaisesRegex(SiteFleetError, "ALREADY_ATTEMPTED"):
            execute_site_cycle("b"*32, transport=self.transport)
        self.assertEqual(len(self.urls), 14)

    def test_ambiguous_failure_is_never_automatically_retried(self):
        def broken(url):
            raise RuntimeError("connection lost")
        with self.assertRaises(RuntimeError):
            execute_site_cycle("c"*32, transport=broken)
        self.assertEqual(AuditLog.objects.filter(action=CLAIM).count(), 1)
        with self.assertRaises(SiteFleetError):
            execute_site_cycle("c"*32, transport=self.transport)
        self.assertEqual(self.urls, [])

    def test_inactive_canonical_identity_prevents_claim(self):
        self.agent.active = False
        self.agent.save(update_fields=["active"])
        with self.assertRaises(SiteFleetError):
            execute_site_cycle("d"*32, transport=self.transport)
        self.assertFalse(AuditLog.objects.filter(action=CLAIM).exists())

    def test_bad_cycle_id_prevents_claim(self):
        with self.assertRaises(SiteFleetError):
            execute_site_cycle("bad", transport=self.transport)
        self.assertEqual(self.urls, [])

    def test_inventory_is_read_only(self):
        out = io.StringIO()
        call_command("mojtaba_site_fleet_cycle", stdout=out)
        self.assertEqual(json.loads(out.getvalue())["canonical_bot"], "mojtaba.bot.ai")
        self.assertFalse(AuditLog.objects.filter(action=CLAIM).exists())

    def test_cli_observation_requires_cycle_id(self):
        with self.assertRaises(CommandError):
            call_command("mojtaba_site_fleet_cycle", "--observe-public")

    def test_cli_cycle_id_requires_observation(self):
        with self.assertRaises(CommandError):
            call_command("mojtaba_site_fleet_cycle", "--cycle-id", "e"*32)
