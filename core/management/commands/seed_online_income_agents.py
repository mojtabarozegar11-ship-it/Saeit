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

AGENTS = [
    ("income-research-agent", "Internet Income Research Agent", "Continuously discover evidence-backed legal online income opportunities."),
    ("income-offer-agent", "Internet Income Offer Agent", "Turn qualified opportunities into concrete products, services and MVP offers."),
    ("income-growth-agent", "Internet Income Growth Agent", "Run measurable lawful growth and conversion experiments under approval boundaries."),
    ("income-audit-agent", "Internet Income Audit Agent", "Audit payments, costs, profit evidence, compliance and learning loops."),
]

ASSIGNMENTS = {
    "income-research-agent": ["income_market_research", "income_opportunity_score"],
    "income-offer-agent": ["income_opportunity_score", "income_offer_design", "income_mvp_build"],
    "income-growth-agent": ["income_growth_experiment", "income_profit_optimize"],
    "income-audit-agent": ["income_revenue_verify", "income_profit_optimize"],
}


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

        for code, name, mission in AGENTS:
            agent, _ = Agent.objects.update_or_create(
                code=code,
                defaults={"name": name, "mission": mission, "risk_level": "medium", "active": True},
            )
            agent.capabilities.set([capabilities[c] for c in ASSIGNMENTS[code]])

        self.stdout.write(self.style.SUCCESS("Online-income agents and capabilities are seeded."))
