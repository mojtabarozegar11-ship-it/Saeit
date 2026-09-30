from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Agent, AgentTask


PIPELINE = [
    ("income-research-agent", "income_market_research"),
    ("income-research-agent", "income_opportunity_score"),
    ("income-offer-agent", "income_offer_design"),
    ("income-offer-agent", "income_mvp_build"),
    ("income-growth-agent", "income_growth_experiment"),
    ("income-audit-agent", "income_revenue_verify"),
    ("income-audit-agent", "income_profit_optimize"),
]


class Command(BaseCommand):
    help = "Queue one auditable online-income pipeline cycle. External actions remain approval-gated."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        queued = 0
        for agent_code, capability_code in PIPELINE:
            agent = Agent.objects.filter(code=agent_code, active=True).first()
            if not agent:
                self.stderr.write(f"Missing active agent: {agent_code}. Run seed_online_income_agents first.")
                continue
            if not agent.capabilities.filter(code=capability_code, active=True).exists():
                self.stderr.write(f"Missing capability {capability_code} on {agent_code}")
                continue
            if options["dry_run"]:
                self.stdout.write(f"DRY RUN: {agent_code} -> {capability_code}")
                continue
            AgentTask.objects.create(
                agent=agent,
                action_type=capability_code,
                capability_code=capability_code,
                risk_snapshot="medium",
                input_data={
                    "objective": "Discover and develop lawful, measurable internet-income opportunities into verified profitable revenue.",
                    "guardrails": [
                        "No pyramid schemes, fraud, spam, deception or platform-policy evasion.",
                        "No external spend, contract, payment or sensitive commitment without the applicable approval grant.",
                        "Revenue is VERIFIED only after reconciled payment evidence.",
                        "Prefer experiments with measurable conversion, margin and repeatability.",
                    ],
                },
                status="queued",
            )
            queued += 1
        self.stdout.write(self.style.SUCCESS(f"Queued {queued} online-income tasks."))
