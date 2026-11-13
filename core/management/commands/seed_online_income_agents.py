from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.canonical_bot_identity import CANONICAL_BOT_CODE, RUNTIME_CODES
from core.models import Agent, AgentCapability


CAPABILITIES = [
    ("factory_native_review", "Factory native evidence review", "Reopen independently reviewed private native build receipts and queue verified specialist/device gaps. No commercial release.", "low"),
    ("factory_f41_private_build", "F41 private blockchain utility build", "Build only bounded vetted F41 orders in the private warehouse; no wallets, network, sales or public deployment.", "low"),
    ("income_market_research", "Internal commercial inventory", "Measure local product inventory and queued tasks. Does not verify external customer demand, competitors, legal feasibility or willingness to pay.", "low"),
    ("income_mojtrade_research_review", "Private MojTrade market evidence review", "Review the one fixed, private, fresh BTC/USD and ETH/USD observation from the existing VPS observer. No network requests, trading, win-rate, PnL, publication, or delivery.", "low"),
    ("income_mojtrade_forward_audit", "Offline forward-market evidence audit", "Review historically recorded and timestamped master-bot observation tasks, model one-hour returns with fixed fees/slippage, and require 30 samples before estimating modeled win rates. No real trade, revenue, scheduling, market requests or commercial release.", "low"),
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
        # Never revive a deliberately disabled master, and never turn a
        # completed handoff into two active runtimes. Lock before modifying
        # capabilities so an unsafe identity state rolls back atomically.
        existing = list(Agent.objects.select_for_update().filter(
            code__in=RUNTIME_CODES,
        ).order_by("code"))
        active = [agent for agent in existing if agent.active]
        if len(active) > 1:
            raise CommandError("MASTER_SEED_MULTIPLE_ACTIVE_RUNTIME_IDENTITIES")
        if existing and not active:
            raise CommandError("MASTER_SEED_REFUSES_INACTIVE_RUNTIME_REACTIVATION")
        master = active[0] if active else None

        capabilities = {}
        for code, name, description, risk in CAPABILITIES:
            obj, _ = AgentCapability.objects.update_or_create(
                code=code,
                defaults={"name": name, "description": description, "risk_level": risk, "active": True},
            )
            capabilities[code] = obj

        code, name, mission = MASTER_AGENT
        if master is None:
            # Backward-compatible fresh bootstrap; the canonical handoff is
            # a separately audited operation, never performed by this seed.
            master = Agent.objects.create(
                code=code, name=name, mission=mission,
                risk_level="medium", active=True,
            )
        else:
            # In particular, do not re-enable the legacy row when the active
            # runtime is already the canonical Mojtaba.bot.ai identity.
            master.name = "Mojtaba.bot.ai" if master.code == CANONICAL_BOT_CODE else name
            master.mission = mission
            master.risk_level = "medium"
            master.save(update_fields=("name", "mission", "risk_level"))
        master.capabilities.set([capabilities[c] for c in ASSIGNMENTS])

        code, name, mission = FACTORY_AGENT
        factory, _ = Agent.objects.update_or_create(
            code=code, defaults={"name": name,"mission": mission,
                                 "risk_level":"low","active":True})
        # Never grant payment, trading, deployment, or other financial tools.
        factory.capabilities.set([capabilities["factory_native_review"], capabilities["factory_f41_private_build"]])

        # Never mass-deactivate existing specialist agents based only on their
        # names. They can have pending tasks or integrations outside this DB.
        # Use consolidate_legacy_agents for preview-first, evidenced retirement.
        # This seeder only owns the master and the dedicated factory identity.

        self.stdout.write(self.style.SUCCESS(
            f"Single active master {master.code} and dedicated moj_1ro_1 factory agent seeded; "
            "no legacy identity reactivation, financial capabilities isolated."
        ))
