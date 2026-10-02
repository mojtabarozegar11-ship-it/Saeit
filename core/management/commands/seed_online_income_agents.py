from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Agent, AgentCapability


CAPABILITIES = [
    ("income_market_research", "Income market research", "Research legal online markets, demand, competitors and payment feasibility.", "low"),
    ("income_opportunity_score", "Income opportunity scoring", "Score opportunities by startup cost, time-to-revenue, margin, scalability, risk and automation potential.", "low"),
    ("income_offer_design", "Offer design", "Design measurable online service, digital product, SaaS, education, content, affiliate or commerce offers.", "medium"),
    ("income_mvp_build", "Revenue MVP build", "Prepare an MVP or sales-ready deliverable without making external financial commitments.", "medium"),
    ("income_growth_experiment", "Growth experiment", "Plan and evaluate lawful acquisition, conversion and retention experiments; no spam or deceptive practices.", "medium"),
    ("income_revenue_verify", "Revenue verification", "Verify revenue only from reconciled payment evidence and reject vanity or unverified revenue claims.", "medium"),
    ("income_profit_optimize", "Profit optimization", "Compare verified revenue, direct costs, margin, repeatability and operational load to improve allocation.", "medium"),
]

MASTER_AGENT = (
    "economic-master-agent",
    "Economic Master Agent",
    "Build the project, remove blockers, create market-ready assets, commercialize them, and increase verified revenue.",
)

ASSIGNMENTS = [code for code, *_ in CAPABILITIES]


class Command(BaseCommand):
    help = "Seed online-income agents and capabilities idempotently."

    @transaction.atomic
    def handle(self, *args, **options):
        capabilities = {}
        for code, name, description, risk in CAPABILITIES:
            obj, _ = AgentCapability.objects.update_or_create(
                code=code,
                defaults={"name": name, "description": description, "risk_level": risk, "active": True},
            )
            capabilities[code] = obj

        code, name, mission = MASTER_AGENT
        agent, _ = Agent.objects.update_or_create(
            code=code,
            defaults={"name": name, "mission": mission, "risk_level": "medium", "active": True},
        )
        agent.capabilities.set([capabilities[c] for c in ASSIGNMENTS])

        # The runtime has one operational economic agent. Legacy split income agents
        # are retained only as historical records and must never receive new work.
        Agent.objects.filter(code__startswith="income-").exclude(code=code).update(active=False)

        self.stdout.write(self.style.SUCCESS("Economic Master Agent and online-income capabilities are seeded; legacy income agents are inactive."))
