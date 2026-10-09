from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from core.models import FactoryRun
from core.recovery_scheduler import RecoveryScheduler


class Command(BaseCommand):
    help = "Run one bounded autonomous non-production Factory cycle from discovery toward launch candidate."

    def add_arguments(self, parser):
        parser.add_argument("--max-runs", type=int, default=5)
        parser.add_argument("--max-steps", type=int, default=20)

    def handle(self, *args, **options):
        if settings.SAEIT_ENV == "production":
            raise RuntimeError("Autonomous staging tick is disabled in production.")
        call_command("seed_factory_agents")
        summary = RecoveryScheduler().recover(limit=50, stale_after_seconds=900)
        call_command("opportunity_discovery_tick", max_opportunities=25)
        call_command("intake_discovered_opportunities", max_intake=10)

        limit = max(1, min(int(options["max_runs"]), 10))
        runs = []
        for run in FactoryRun.objects.filter(status="active").order_by("updated_at", "pk"):
            if isinstance(run.constraints, dict) and run.constraints.get("source_stage") == "opportunity_discovery":
                runs.append(run)
                if len(runs) >= limit:
                    break
        for run in runs:
            # Rotate waiting runs so other products get scheduled.
            FactoryRun.objects.filter(pk=run.pk, status="active").update(updated_at=timezone.now())
            call_command(
                "autonomous_master_loop",
                factory=True,
                run_id=run.run_id,
                goal=run.goal,
                max_steps=max(1, min(int(options["max_steps"]), 30)),
            )
        self.stdout.write(self.style.SUCCESS(
            f"FACTORY_TICK_OK recovered={summary.recovered} failed={summary.failed} processed_runs={len(runs)}"
        ))
