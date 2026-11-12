from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.knowledge_agent import DEFAULT_OUTLINE, queue_cycle, seed_library
from core.knowledge_agent_models import KnowledgeAgentPlan, KnowledgeAgentRun
from core.models import Agent, AgentTask
from core.unified_bot_identity import BOT_CODE


class KnowledgeAgentSchedulerTests(TestCase):
    def setUp(self):
        self.bot = Agent.objects.create(
            code=BOT_CODE, name="Mojtaba.bot.ai", mission="Canonical owner",
            active=True,
        )
    def test_scheduler_creates_one_run_and_respects_cadence(self):
        plan = KnowledgeAgentPlan.objects.create(
            code="knowledge-content-director", title="Scheduler Test", mission="test", goal="test",
            cadence_hours=24, active=True, require_owner_approval=True,
        )
        first = queue_cycle()
        self.assertIsNotNone(first)
        self.assertEqual(KnowledgeAgentRun.objects.filter(plan=first.plan).count(), 1)
        task = AgentTask.objects.get(action_type="knowledge_content_generation", input_data__run_id=first.pk)
        self.assertEqual(task.risk_snapshot, "high")
        self.assertEqual(task.agent_id, self.bot.pk)
        self.assertFalse(Agent.objects.filter(code="knowledge-content-director").exists())
        self.assertTrue(task.input_data["paid_model"])
        self.assertTrue(first.approval_required)
        self.assertIsNotNone(first.plan.next_run_at)
        self.assertIsNone(queue_cycle())
        first.plan.next_run_at = timezone.now() - timedelta(minutes=1)
        first.plan.save(update_fields=["next_run_at", "updated_at"])
        # The existing queued run still blocks duplicate execution.
        self.assertIsNone(queue_cycle())

    def test_seed_repairs_outline_on_existing_book(self):
        plan = KnowledgeAgentPlan.objects.create(
            code="knowledge-content-director", title="Outline Test", mission="test", goal="test",
        )
        from core.knowledge_agent_models import KnowledgeBook, KnowledgeDomain
        domain = KnowledgeDomain.objects.create(
            code="food-agriculture", title="حوزه موجود", scientific_scope="test", priority=1,
        )
        KnowledgeBook.objects.create(
            plan=plan, domain_ref=domain, code="food-agriculture", title="کتاب موجود",
            domain="حوزه موجود", objective="test", outline=[],
        )
        seed_library()
        book = KnowledgeBook.objects.get(code="food-agriculture")
        self.assertEqual(book.outline, DEFAULT_OUTLINE)

    def test_command_reports_existing_queued_run_instead_of_false_completion(self):
        output = StringIO()
        call_command("knowledge_agent_cycle", stdout=output)
        self.assertIn("KNOWLEDGE_AGENT: queued run=", output.getvalue())

        output = StringIO()
        call_command("knowledge_agent_cycle", stdout=output)
        self.assertIn("KNOWLEDGE_AGENT: awaiting_execution queued=1 running=0", output.getvalue())
        self.assertNotIn("library complete", output.getvalue())
        self.assertEqual(KnowledgeAgentRun.objects.count(), 1)

    def test_command_reports_inactive_plan_without_false_completion(self):
        plan = KnowledgeAgentPlan.objects.create(
            code="knowledge-content-director", title="Paused", mission="paused", goal="paused",
            active=False,
        )
        output = StringIO()
        call_command("knowledge_agent_cycle", stdout=output)
        self.assertIn("KNOWLEDGE_AGENT: inactive", output.getvalue())
        self.assertEqual(KnowledgeAgentRun.objects.filter(plan=plan).count(), 0)

    def test_active_legacy_blocks_without_creating_books_or_paid_tasks(self):
        Agent.objects.create(
            code="knowledge-content-director", name="Legacy",
            mission="Knowledge", active=True,
        )
        from core.knowledge_agent_models import KnowledgeBook
        with self.assertRaisesRegex(RuntimeError, "MOJTABA_LEGACY_HANDOFF_REQUIRED"):
            queue_cycle()
        self.assertEqual(KnowledgeAgentPlan.objects.count(), 0)
        self.assertEqual(KnowledgeBook.objects.count(), 0)
        self.assertEqual(AgentTask.objects.count(), 0)

    def test_inactive_legacy_with_queued_task_is_not_silently_migrated(self):
        legacy = Agent.objects.create(
            code="knowledge-content-director", name="Legacy",
            mission="Knowledge", active=False,
        )
        task = AgentTask.objects.create(
            agent=legacy, action_type="knowledge_content_generation",
            capability_code="research-write-review", status="queued",
        )
        with self.assertRaisesRegex(RuntimeError, "MOJTABA_LEGACY_HANDOFF_REQUIRED"):
            queue_cycle()
        task.refresh_from_db()
        self.assertEqual(task.agent_id, legacy.pk)
        self.assertEqual(task.status, "queued")
        self.assertFalse(KnowledgeAgentRun.objects.exists())

    def test_missing_canonical_does_not_create_paid_tasks_or_plan(self):
        self.bot.active = False
        self.bot.save(update_fields=["active"])
        output = StringIO()
        call_command("knowledge_agent_cycle", stdout=output)
        self.assertIn("blocked_pending_single_bot_handoff", output.getvalue())
        self.assertEqual(KnowledgeAgentPlan.objects.count(), 0)
        self.assertEqual(AgentTask.objects.count(), 0)

    def test_inactive_legacy_without_pending_work_is_preserved(self):
        legacy = Agent.objects.create(
            code="knowledge-content-director", name="Legacy",
            mission="Knowledge", active=False,
        )
        run = queue_cycle()
        self.assertIsNotNone(run)
        legacy.refresh_from_db()
        self.assertFalse(legacy.active)
        self.assertEqual(AgentTask.objects.get(input_data__run_id=run.pk).agent_id, self.bot.pk)
