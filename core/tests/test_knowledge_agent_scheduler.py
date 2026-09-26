from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.knowledge_agent import DEFAULT_OUTLINE, queue_cycle, seed_library
from core.knowledge_agent_models import KnowledgeAgentPlan, KnowledgeAgentRun


class KnowledgeAgentSchedulerTests(TestCase):
    def test_scheduler_creates_one_run_and_respects_cadence(self):
        plan = KnowledgeAgentPlan.objects.create(
            code="knowledge-content-director", title="Scheduler Test", mission="test", goal="test",
            cadence_hours=24, active=True, require_owner_approval=True,
        )
        first = queue_cycle()
        self.assertIsNotNone(first)
        self.assertEqual(KnowledgeAgentRun.objects.filter(plan=first.plan).count(), 1)
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
