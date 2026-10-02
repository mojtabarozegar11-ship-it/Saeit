from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Agent, AgentTask


MASTER_AGENT_CODE = "economic-master-agent"
PIPELINE = [
    "income_market_research",
    "income_opportunity_score",
    "income_offer_design",
    "income_mvp_build",
    "income_growth_experiment",
    "income_revenue_verify",
    "income_profit_optimize",
]


class Command(BaseCommand):
    help = "Queue exactly one concrete next economic action for the single master agent."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        agent = Agent.objects.filter(code=MASTER_AGENT_CODE, active=True).first()
        if not agent:
            self.stderr.write("Missing active economic-master-agent. Run seed_online_income_agents first.")
            return

        # Never manufacture more work while a prior economic action is unfinished.
        active = AgentTask.objects.filter(
            agent=agent,
            capability_code__startswith="income_",
            status__in=("queued", "running", "blocked"),
        ).order_by("created_at").first()
        if active:
            self.stdout.write(f"WAITING: task {active.pk} must reach a verified terminal result first.")
            return

        completed = set(
            AgentTask.objects.filter(
                agent=agent,
                capability_code__startswith="income_",
                status="completed",
                output_data__verified_effect=True,
            ).values_list("capability_code", flat=True)
        )
        capability_code = next((code for code in PIPELINE if code not in completed), PIPELINE[0])

        if not agent.capabilities.filter(code=capability_code, active=True).exists():
            self.stderr.write(f"Missing capability {capability_code} on {MASTER_AGENT_CODE}")
            return

        if options["dry_run"]:
            self.stdout.write(f"DRY RUN: {MASTER_AGENT_CODE} -> {capability_code}")
            return

        task = AgentTask.objects.create(
            agent=agent,
            action_type=capability_code,
            capability_code=capability_code,
            risk_snapshot="medium",
            input_data={
                "objective": "Complete one concrete, highest-impact step toward a finished project and verified lawful revenue.",
                "execution_contract": {
                    "one_cycle_one_concrete_action": True,
                    "must_execute_not_just_report": True,
                    "success_requires_verified_effect": True,
                    "blocker_becomes_remediation_work": True,
                },
                "guardrails": [
                    "No fraud, spam, deception or platform-policy evasion.",
                    "No external spend, contract, payment or sensitive commitment without applicable approval.",
                    "Revenue is verified only after reconciled external payment evidence.",
                ],
            },
            status="queued",
        )
        self.stdout.write(self.style.SUCCESS(
            f"QUEUED concrete task {task.pk}: {MASTER_AGENT_CODE} -> {capability_code}"
        ))
