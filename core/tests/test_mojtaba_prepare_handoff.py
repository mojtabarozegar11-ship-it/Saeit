import io
import json
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from core.models import Agent, AgentTask, AgentCapability
from core.unified_bot_identity import BOT_CODE

class PrepareHandoffTests(TestCase):
    def setUp(self):
        self.old = Agent.objects.create(code="economic-master-agent",
            name="Legacy", mission="Preserve", active=True)
        self.task = AgentTask.objects.create(agent=self.old, action_type="legacy",
            status="queued")

    def run_prepare(self, *args):
        out = io.StringIO()
        call_command("mojtaba_prepare_handoff", *args, stdout=out)
        return json.loads(out.getvalue())

    def test_default_preview_creates_no_identity(self):
        report = self.run_prepare()
        self.assertFalse(report["canonical_active"])
        self.assertIsNone(report["live_worker_count"])
        self.assertEqual(report["other_active_records"], 1)
        self.assertEqual(report["registered_agents"][0]["unreconciled_tasks"], 1)
        self.assertFalse(Agent.objects.filter(code=BOT_CODE).exists())

    def test_provision_requires_both_flags(self):
        for flag in ("--provision-site-only", "--confirm-maintenance-window"):
            with self.assertRaises(CommandError):
                self.run_prepare(flag)
        self.assertFalse(Agent.objects.filter(code=BOT_CODE).exists())

    def test_provision_preserves_all_legacy_and_grants_nothing(self):
        flags = ("--provision-site-only", "--confirm-maintenance-window")
        result = self.run_prepare(*flags)
        bot = Agent.objects.get(code=BOT_CODE)
        self.assertTrue(result["canonical_record_created"])
        self.assertTrue(bot.active)
        self.assertEqual(bot.capabilities.count(), 0)
        self.assertEqual(AgentCapability.objects.count(), 0)
        self.old.refresh_from_db()
        self.task.refresh_from_db()
        self.assertTrue(self.old.active)
        self.assertEqual(self.task.agent_id, self.old.pk)
        self.assertFalse(result["factory_started"])
        self.assertFalse(self.run_prepare(*flags)["canonical_record_created"])

    def test_inactive_canonical_never_reactivated(self):
        Agent.objects.create(code=BOT_CODE, name="Canonical", mission="Hold", active=False)
        with self.assertRaises(CommandError):
            self.run_prepare("--provision-site-only", "--confirm-maintenance-window")
        self.assertFalse(Agent.objects.get(code=BOT_CODE).active)

    def test_old_seeder_cannot_recreate_legacy_after_canonical_provision(self):
        self.run_prepare("--provision-site-only", "--confirm-maintenance-window")
        with self.assertRaisesRegex(CommandError, "LEGACY_SEED_DISABLED"):
            call_command("seed_online_income_agents")
        self.assertFalse(Agent.objects.filter(code="moj_1ro_1").exists())
        self.assertEqual(AgentCapability.objects.count(), 0)

    def test_unknown_status_is_unreconciled(self):
        self.task.status = "unrecognized"
        self.task.save(update_fields=["status"])
        result = self.run_prepare()
        self.assertEqual(result["registered_agents"][0]["unreconciled_tasks"], 1)
        self.assertFalse(result["retirement_authorized"])
