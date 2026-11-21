"""Proof that a shared bot identity and its audit do not mutate production lanes."""
import io
import json
from django.core.management import call_command
from django.test import TestCase

from core.bot_identity import (
    canonical_bot_id, enforce_single_top_level_bot, summarize_internal_agent_registry
)
from core.models import Agent, AgentTask, AuditLog
from core.unified_bot_identity import (
    BOT_CODE, module_for_capability, non_factory_task_scope,
)
from mojtaba_identity import BOT_ID


class MojtabaCanonicalReadOnlyTests(TestCase):
    def test_only_one_declared_public_identity(self):
        self.assertEqual(BOT_ID, "mojtaba.bot.ai")
        self.assertEqual(BOT_CODE, "mojtaba-bot-ai")
        self.assertEqual(canonical_bot_id(" MOJTABA.BOT.AI "), BOT_ID)
        self.assertEqual(enforce_single_top_level_bot(["mojtaba.bot.ai"]), BOT_ID)
        for names in ([], ["mojtaba.bot.ai", "other.bot"], ["other.bot"]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                enforce_single_top_level_bot(names)

    def test_legacy_registry_is_not_a_list_of_deployed_bots(self):
        rows = [
            {"code": "factory-master-agent", "active": True},
            {"code": "newsletter-specialist", "active": True},
        ]
        result = summarize_internal_agent_registry(rows)
        self.assertEqual(result["declared_top_level_bot_count"], 1)
        self.assertEqual(result["django_component_records"], 2)
        self.assertIs(result["runtime_process_topology_attested"], False)
        with self.assertRaises(ValueError):
            summarize_internal_agent_registry(rows + rows[:1])

    def test_factory_tasks_are_not_implicitly_migrated_to_bot(self):
        agent = Agent.objects.create(
            code="factory-market-research-agent",
            name="Research", mission="Retain pending work", active=True
        )
        preserved = AgentTask.objects.create(
            agent=agent, action_type="factory_native_review",
            capability_code="factory_native_review", status="queued",
        )
        needs_review = AgentTask.objects.create(
            agent=agent, action_type="product_research",
            capability_code="product_research", status="blocked",
        )
        review_ids = set(
            AgentTask.objects.filter(non_factory_task_scope())
            .values_list("pk", flat=True)
        )
        self.assertNotIn(preserved.pk, review_ids)
        self.assertIn(needs_review.pk, review_ids)
        self.assertEqual(module_for_capability("product_research"),
                         "unmapped_requires_adapter_review")

    def test_command_reports_actual_registry_without_creating_canonical_owner(self):
        factory = Agent.objects.create(
            code="factory-market-research-agent", name="Research",
            mission="Do not activate anything", active=True
        )
        AgentTask.objects.create(
            agent=factory, action_type="product_research",
            capability_code="product_research", status="queued"
        )
        AgentTask.objects.create(
            agent=factory, action_type="product_research",
            capability_code="product_research", status="blocked"
        )
        out = io.StringIO()
        call_command("mojtaba_runtime_inventory", stdout=out)
        report = json.loads(out.getvalue())
        self.assertEqual(report["product_id"], BOT_ID)
        self.assertEqual(report["canonical_agent_rows"], 0)
        self.assertEqual(report["canonical_active_rows"], 0)
        self.assertEqual(report["nonterminal_task_count"], 2)
        self.assertEqual(report["registered_agent_rows"], 1)
        self.assertEqual(report["chat_session_count"], 0)
        self.assertEqual(report["chat_message_count"], 0)
        self.assertFalse(report["single_worker_attested"])
        self.assertFalse(report["authenticated_inference_attested"])
        self.assertFalse(report["income_attested"])
        self.assertEqual(
            report["release_gate"],
            "BLOCKED_NEEDS_RUNTIME_HANDOFF_AND_LIVE_RECEIPT",
        )
        self.assertFalse(Agent.objects.filter(code=BOT_CODE).exists())
        self.assertEqual(AgentTask.objects.count(), 2)
        self.assertFalse(AuditLog.objects.exists())
