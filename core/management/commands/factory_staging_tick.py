from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.recovery_scheduler import RecoveryScheduler


class Command(BaseCommand):
    help = "Run one safe non-production factory maintenance, discovery, and research-intake cycle."

    def handle(self, *args, **options):
        call_command("seed_factory_agents")
        summary = RecoveryScheduler().recover(limit=50, stale_after_seconds=900)
        call_command("opportunity_discovery_tick", max_opportunities=25)
        call_command("intake_discovered_opportunities", max_intake=10)
        self.stdout.write(self.style.SUCCESS(
            f"FACTORY_TICK_OK recovered={summary.recovered} failed={summary.failed}"
        ))
