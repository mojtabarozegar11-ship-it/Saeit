import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.opportunity_discovery import OpportunityDiscovery


class Command(BaseCommand):
    help = "Run Stage-1 discovery and atomically persist the latest non-production report."

    def add_arguments(self, parser):
        parser.add_argument("--max-opportunities", type=int, default=25)
        parser.add_argument("--output", default="var/factory/discovery/latest.json")

    def handle(self, *args, **opts):
        if settings.SAEIT_ENV == "production":
            raise CommandError("Discovery tick is disabled in production.")
        report = OpportunityDiscovery().discover(max_opportunities=opts["max_opportunities"])
        if report["status"] != "PASS":
            raise CommandError("Discovery produced no evidence-backed opportunities.")
        output = Path(opts["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + ".tmp")
        temp.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        temp.replace(output)
        self.stdout.write(json.dumps({
            "status": "PASS",
            "opportunity_count": report["opportunity_count"],
            "output": str(output),
            "next_stage": report["next_stage"],
        }, sort_keys=True))
