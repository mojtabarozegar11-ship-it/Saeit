from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Agent, AgentTask


MASTER_CODES = ("moj_1ro_1", "economic-master-agent")
ACTION = "implement_feature"


class Command(BaseCommand):
    help = "Queue exactly one concrete, auditable master-agent work item."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        agent = None
        for code in MASTER_CODES:
            agent = Agent.objects.filter(code=code, active=True).first()
            if agent:
                break
        if not agent:
            self.stderr.write("No active master agent found (moj_1ro_1/economic-master-agent).")
            return

        # Never manufacture activity while prior work is still actionable.
        existing = AgentTask.objects.filter(
            agent=agent, status__in=("queued", "running", "blocked")
        ).order_by("id").first()
        if existing:
            self.stdout.write(
                f"Existing work retained: task={existing.pk} action={existing.action_type} status={existing.status}"
            )
            return

        capability = agent.capabilities.filter(code=ACTION, active=True).first()
        if not capability:
            self.stderr.write(
                f"Master agent lacks real capability '{ACTION}'. "
                "Cycle stopped instead of creating a fake/report-only task."
            )
            return

        payload = {
            "primary_goal": "Complete the project and create verified lawful revenue.",
            "work_selection": "highest_impact_unfinished_work",
            "definition_of_done": [
                "one concrete named deliverable is changed or created",
                "the change is verified by evidence/test/state",
                "a blocker is never reported as success",
                "research/report text alone is never success",
            ],
            "blocker_policy": "record exact blocker, create remediation work, then continue",
            "revenue_policy": "count revenue only after external settlement evidence and reconciliation",
        }

        if options["dry_run"]:
            self.stdout.write(f"DRY RUN: {agent.code} -> {ACTION}")
            return

        task = AgentTask.objects.create(
            agent=agent,
            action_type=ACTION,
            capability_code=capability.code,
            risk_snapshot=capability.risk_level or "low",
            input_data=payload,
            status="queued",
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Queued concrete master work: task={task.pk} agent={agent.code} action={ACTION}"
            )
        )
