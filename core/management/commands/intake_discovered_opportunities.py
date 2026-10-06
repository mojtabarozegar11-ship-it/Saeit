import json
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from core.autonomous_brain import AutonomousBrain
from core.models import FactoryRun


class Command(BaseCommand):
    help = "Feed persisted Stage-1 opportunities into independent Stage-2 Factory research runs."

    def add_arguments(self, parser):
        parser.add_argument("--input", default="var/factory/discovery/latest.json")
        parser.add_argument("--max-intake", type=int, default=10)

    def handle(self, *args, **opts):
        path = Path(opts["input"])
        if not path.exists():
            raise CommandError("No persisted Stage-1 discovery report exists.")
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("status") != "PASS" or not report.get("real_research"):
            raise CommandError("Stage-1 report is not real-research PASS evidence.")
        opportunities = report.get("opportunities") or []
        limit = max(1, min(int(opts["max_intake"]), 25))
        queued = []
        brain = AutonomousBrain()
        for item in opportunities[:limit]:
            oid = str(item.get("opportunity_id") or "").strip()
            problem = str(item.get("problem") or "").strip()
            urls = item.get("evidence_urls") or []
            if not oid or not problem or not urls:
                continue
            existing = next((run for run in FactoryRun.objects.order_by("-created_at")[:500]
                             if isinstance(run.constraints, dict)
                             and run.constraints.get("discovery_opportunity_id") == oid), None)
            if existing:
                queued.append({"opportunity_id": oid, "run_id": existing.run_id, "status": "existing"})
                continue
            goal = (
                "Research this evidence-backed product opportunity and determine whether it "
                f"deserves progression through the Product Factory. Opportunity {oid}. "
                f"Problem signal: {problem[:900]}"
            )
            task = brain.plan_product_factory_step(
                payload={
                    "goal": goal,
                    "constraints": {
                        "discovery_opportunity_id": oid,
                        "discovery_evidence_urls": urls[:6],
                        "source_stage": "opportunity_discovery",
                    },
                }
            )
            queued.append({"opportunity_id": oid, "task_id": task.pk, "run_id": task.factory_run.run_id, "status": "queued"})
        if not queued:
            raise CommandError("No valid Stage-1 opportunities were eligible for Stage-2 intake.")
        self.stdout.write(json.dumps({"status": "PASS", "queued": queued}, sort_keys=True))
