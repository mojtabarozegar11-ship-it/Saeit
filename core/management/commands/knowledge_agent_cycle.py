from django.core.management.base import BaseCommand
from django.utils import timezone
from core.knowledge_agent import queue_cycle
from core.knowledge_agent_models import KnowledgeAgentPlan


class Command(BaseCommand):
    help = "Queue the next planned Knowledge Content Director cycle."

    def handle(self, *args, **options):
        run = queue_cycle()
        if run is None:
            plan = KnowledgeAgentPlan.objects.get(code="knowledge-content-director")
            queued = plan.runs.filter(status="queued").count()
            running = plan.runs.filter(status="running").count()
            if queued or running:
                self.stdout.write(
                    f"KNOWLEDGE_AGENT: awaiting_execution queued={queued} running={running}"
                )
            elif not plan.active:
                self.stdout.write("KNOWLEDGE_AGENT: inactive")
            elif plan.next_run_at and plan.next_run_at > timezone.now():
                self.stdout.write("KNOWLEDGE_AGENT: cadence_wait")
            elif plan.books.exclude(status="published").exists():
                self.stdout.write("KNOWLEDGE_AGENT: no_run_created requires_review=true")
            else:
                self.stdout.write(self.style.SUCCESS("KNOWLEDGE_AGENT: library complete"))
            return
        self.stdout.write(self.style.SUCCESS(f"KNOWLEDGE_AGENT: queued run={run.pk} book={run.book.code}"))
