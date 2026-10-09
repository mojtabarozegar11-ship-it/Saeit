import json

from django.core.management.base import BaseCommand, CommandError

from core.opportunity_discovery import OpportunityDiscovery


class Command(BaseCommand):
    help = "Run bounded autonomous Stage-1 Opportunity Discovery and emit JSON."

    def add_arguments(self, parser):
        parser.add_argument("--max-opportunities", type=int, default=25)
        parser.add_argument("--seed", action="append", default=[])

    def handle(self, *args, **opts):
        try:
            report = OpportunityDiscovery().discover(
                seeds=opts["seed"] or None,
                max_opportunities=opts["max_opportunities"],
            )
        except Exception as exc:
            raise CommandError(f"Opportunity discovery blocked: {exc}") from exc
        self.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True))
        if report["status"] != "PASS":
            raise CommandError("Opportunity discovery produced no evidence-backed opportunities.")
