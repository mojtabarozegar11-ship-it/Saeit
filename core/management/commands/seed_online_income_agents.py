from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Agent, AgentCapability


CAPABILITIES = [
    ("factory_native_review", "Factory native evidence review", "Reopen independently reviewed private native build receipts and queue verified specialist/device gaps. No commercial release.", "low"),
    ("factory_f41_private_build", "F41 private blockchain utility build", "Build only bounded vetted F41 orders in the private warehouse; no wallets, network, sales or public deployment.", "low"),
    ("income_market_research", "Internal commercial inventory", "Measure local product inventory and queued tasks. Does not verify external customer demand, competitors, legal feasibility or willingness to pay.", "low"),
    ("income_inbound_lead_review", "Private inbound inquiry intake", "Route genuine stored commercial/project/technology inquiries for private review; no contact, price commitment, or revenue claim.", "low"),
    ("income_opportunity_score", "Product baseline inventory", "Record the existing catalog for later evaluation. Does not score market margins, startup costs or demand until external evidence exists.", "low"),
    ("income_offer_design", "Private draft offer design", "Create one inactive, zero-price internal draft service offer. No seller claim, customer contact, public listing or payment activation.", "medium"),
    ("income_mvp_build", "Revenue MVP build", "Prepare an MVP or sales-ready deliverable without making external financial commitments.", "medium"),
    ("income_growth_experiment", "Internal growth hypothesis", "Record a private acquisition hypothesis for an existing MVP; no public experiment, spend, conversion measurement or customer outreach.", "medium"),
    ("income_revenue_verify", "Revenue verification", "Verify revenue only from reconciled payment evidence and reject vanity or unverified revenue claims.", "medium"),
    ("income_profit_optimize", "Catalog profit baseline", "Inspect active catalog items. Do not claim profit optimization or verified margin without independent revenue and cost evidence.", "medium"),
    ("master_self_improvement", "Master self-improvement audit", "Run the bounded private source-upgrade engine, test allowlisted repairs, and record immutable before/after evidence. Never promote unreviewed code.", "medium"),
]

MASTER_AGENT = (
    "economic-master-agent",
    "Economic Master Agent",
    "Continuously improve the agent and factory through evidenced upgrades; manage projects, products, lawful trade and customer delivery; increase settled cash profit; fund essential operating costs only from collected revenue within an auditable preauthorized budget.",
)

ASSIGNMENTS = [code for code, *_ in CAPABILITIES if code not in ("factory_native_review", "factory_f41_private_build")]

FACTORY_AGENT = ("moj_1ro_1","MOJ Factory Orchestrator",
    "Route verified F41 private work orders and six native specialist tests without commercial release.")


class Command(BaseCommand):
    help = "Seed online-income agents and capabilities idempotently."

    @transaction.atomic
    def handle(self, *args, **options):
        capabilities = {}
        created_codes = set()
        for code, name, description, risk in CAPABILITIES:
            obj, created = AgentCapability.objects.get_or_create(
                code=code,
                defaults={"name": name, "description": description, "risk_level": risk, "active": True},
            )
            if created:
                created_codes.add(code)
            capabilities[code] = obj

        code, name, mission = MASTER_AGENT
        agent, created_agent = Agent.objects.get_or_create(
            code=code,
            defaults={"name": name, "mission": mission, "risk_level": "medium", "active": True},
        )
        # Seed missing low/medium-risk internal grants, but never resurrect an
        # existing revoked capability, removed assignment or inactive agent.
        # Existing permissions and risk levels are owner-controlled state.
        agent.capabilities.add(*[
            capabilities[c] for c in ASSIGNMENTS
            if capabilities[c].active and (created_agent or c in created_codes)
        ])

        code, name, mission = FACTORY_AGENT
        factory, created_factory = Agent.objects.get_or_create(
            code=code, defaults={"name": name,"mission": mission,
                                 "risk_level":"low","active":True})
        # Never grant payment, trading, deployment, or other financial tools.
        # Factory permission changes are independent from the economic master.
        if created_factory:
            factory.capabilities.add(*[
                capabilities[c] for c in ("factory_native_review", "factory_f41_private_build")
                if capabilities[c].active
            ])

        # Never mass-deactivate existing specialist agents based only on their
        # names. They can have pending tasks or integrations outside this DB.
        # Use consolidate_legacy_agents for preview-first, evidenced retirement.
        # This seeder only owns the master and the dedicated factory identity.

        self.stdout.write(self.style.SUCCESS(
            "Economic master and factory identities ensured without overriding existing grants, "
            "activation flags, or risk policy."
        ))
