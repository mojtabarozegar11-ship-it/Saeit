"""Read-only stage-4 research diagnostics; no network requests or state mutation."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from core.models import AgentTask, FactoryRun, Product, ResearchProject


class Command(BaseCommand):
    help = "Summarize persisted stage-4 research blockers without exposing evidence or secrets."

    def handle(self, *args, **options):
        if getattr(settings, "SAEIT_ENV", "") == "production":
            raise CommandError("Use staging for stage-4 diagnostics.")
        waiting = Product.objects.filter(metadata__factory_state="needs_research")
        total = waiting.count()
        self.stdout.write(f"STAGE4_PRODUCTS_WAITING={total}")
        for status, count in sorted(
            (str(row["status"]), row["total"])
            for row in AgentTask.objects.filter(action_type="product_research")
            .values("status").annotate(total=Count("pk"))
        ):
            self.stdout.write(f"RESEARCH_TASK_STATUS {status}={count}")
        evidence_count = ResearchProject.objects.filter(evidence__isnull=False).distinct().count()
        waiting_retry = 0
        exhausted = 0
        for metadata in waiting.values_list("metadata", flat=True).iterator(chunk_size=200):
            validation = (metadata or {}).get("validation") or {}
            stage4 = validation.get("stage4_research") or {}
            exhausted += stage4.get("status") == "capacity_exhausted"
            waiting_retry += stage4.get("status") in {"waiting_for_evidence", "retry_scheduled"}
        self.stdout.write(f"STAGE4_CAPACITY_EXHAUSTED={exhausted} STAGE4_RETRY_PENDING={waiting_retry}")
        self.stdout.write(f"RESEARCH_PROJECTS_WITH_EVIDENCE={evidence_count}")
        provider_path = str(getattr(settings, "FACTORY_RESEARCH_PROVIDER", "") or "").strip()
        self.stdout.write(f"RESEARCH_PROVIDER_CONFIGURED={int(bool(provider_path))}")
        self.stdout.write(
            f"RESEARCH_PROJECTS_WITH_REAL_SOURCE="
            f"{ResearchProject.objects.filter(sources__provenance__real_research=True).distinct().count()}"
        )
        self.stdout.write(
            f"RESEARCH_PROJECTS={ResearchProject.objects.count()} "
            f"ACTIVE_RUNS={FactoryRun.objects.filter(status='active').count()}"
        )
        self.stdout.write("STAGE4_DIAGNOSTIC_ONLY no evidence fetch, no transition, no approval bypass")
