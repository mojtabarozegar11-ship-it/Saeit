from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F

from core.models import Agent, AgentCapability, AgentTask, AuditLog
from core.unified_bot_identity import BOT_CODE, BOT_NAME, LEGACY_EXECUTOR_CODES


CAPABILITIES = [
    ("factory_native_review", "Factory native evidence review", "Reopen independently reviewed private native build receipts and queue verified specialist/device gaps. No commercial release.", "low"),
    ("factory_f41_private_build", "F41 private blockchain utility build", "Build only bounded vetted F41 orders in the private warehouse; no wallets, network, sales or public deployment.", "low"),
    ("income_market_research", "Internal commercial inventory", "Measure local product inventory and queued tasks. Does not verify external customer demand, competitors, legal feasibility or willingness to pay.", "low"),
    ("income_opportunity_score", "Product baseline inventory", "Record the existing catalog for later evaluation. Does not score market margins, startup costs or demand until external evidence exists.", "low"),
    ("income_offer_design", "Private draft offer design", "Create one inactive, zero-price internal draft service offer. No seller claim, customer contact, public listing or payment activation.", "medium"),
    ("income_mvp_build", "Revenue MVP build", "Prepare an MVP or sales-ready deliverable without making external financial commitments.", "medium"),
    ("income_growth_experiment", "Internal growth hypothesis", "Record a private acquisition hypothesis for an existing MVP; no public experiment, spend, conversion measurement or customer outreach.", "medium"),
    ("income_revenue_verify", "Revenue verification", "Verify revenue only from reconciled payment evidence and reject vanity or unverified revenue claims.", "medium"),
    ("income_profit_optimize", "Catalog profit baseline", "Inspect active catalog items. Do not claim profit optimization or verified margin without independent revenue and cost evidence.", "medium"),
    ("master_self_improvement", "Master self-improvement audit", "Run the bounded private source-upgrade engine, test allowlisted repairs, and record immutable before/after evidence. Never promote unreviewed code.", "medium"),
    ("research-write-review", "Knowledge library draft generation", "Queue evidence-bound research drafts only. Paid model generation requires an explicit one-time owner grant; no automatic paid API call or publication.", "high"),
    ("content-editorial-draft", "Owner newsletter draft processing", "Transform a real queued owner submission into an internal review draft with provenance. No public publish, external messages or autonomous spending.", "low"),
]

MASTER_AGENT = (
    BOT_CODE,
    BOT_NAME,
    "Continuously improve the agent and factory through evidenced upgrades; manage projects, products, lawful trade and customer delivery; increase settled cash profit; fund essential operating costs only from collected revenue within an auditable preauthorized budget.",
)

ASSIGNMENTS = [code for code, *_ in CAPABILITIES]


class Command(BaseCommand):
    help = "Seed one Mojtaba.bot.ai owner and merge the two proven internal executors."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply-legacy-merge", action="store_true",
            help="Explicitly reassign idle legacy economic/factory tasks and retire old identities",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # Do not change the identity of an in-flight job: its original worker
        # might already have executed an irreversible effect. The entire seed
        # must fail atomically, without partially modifying ownership.
        predecessors = list(Agent.objects.select_for_update().filter(
            code__in=LEGACY_EXECUTOR_CODES
        ).order_by("pk"))
        if not options["apply_legacy_merge"] and any(
            old.active or AgentTask.objects.filter(agent=old).exclude(
                status__in=("completed", "failed", "cancelled")
            ).exists()
            for old in predecessors
        ):
            raise CommandError(
                "UNIFIED_BOT_LEGACY_MERGE_REQUIRES_EXPLICIT_APPLY"
            )
        running = AgentTask.objects.filter(
            agent__code__in=LEGACY_EXECUTOR_CODES, status="running"
        ).order_by("pk").first()
        if running:
            raise CommandError(
                f"UNIFIED_BOT_MIGRATION_BLOCKED_RUNNING_TASK={running.pk}"
            )
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
        # Both economic and private factory capabilities now belong to the
        # one bot. Its gateway still enforces each capability's risk snapshot.
        agent.capabilities.set([capabilities[c] for c in ASSIGNMENTS])

        for old in predecessors:
            old_code = old.code
            # A pending job may be moved only if its action is implemented in
            # the new bot. Unknown work must be reviewed, not lost/relabelled.
            # Terminal task ownership is immutable provenance. A blocked or
            # unrecognized status may carry an outstanding owner approval,
            # external effect, or unresolved retry; never silently reassign it.
            unreconciled = AgentTask.objects.filter(agent=old).exclude(
                status__in=("queued", "completed", "failed", "cancelled")
            ).order_by("pk").first()
            if unreconciled:
                raise CommandError(
                    f"UNIFIED_BOT_MIGRATION_BLOCKED_UNRECONCILED_TASK={unreconciled.pk}"
                )
            queued = AgentTask.objects.filter(agent=old, status="queued")
            unknown = queued.exclude(capability_code__in=ASSIGNMENTS).order_by("pk").first()
            if unknown:
                raise CommandError(
                    f"UNIFIED_BOT_UNMAPPED_LEGACY_TASK={unknown.pk}"
                )
            mismatched = queued.exclude(action_type=F("capability_code")).order_by("pk").first()
            if mismatched:
                raise CommandError(
                    f"UNIFIED_BOT_MISMATCHED_LEGACY_TASK={mismatched.pk}"
                )
            # Only unstarted, supported tasks change owner. Historical
            # completed/failed/cancelled tasks remain attached to their
            # original Agent, preserving audit and delivery attribution.
            historical_retained = AgentTask.objects.filter(
                agent=old, status__in=("completed", "failed", "cancelled")
            ).count()
            queued_reassigned = queued.update(agent=agent)
            if old.active:
                old.active = False
                old.save(update_fields=["active", "updated_at"])
            # Do not delete the old identity; FK links and audit records must
            # remain available while external schedulers are inventoried.
            AuditLog.objects.get_or_create(
                action="internal_executor_merged",
                target_type="Agent",
                target_id=str(old.pk),
                defaults={
                    "actor_type": "system", "actor_id": BOT_CODE,
                    "before_state": {"code": old_code},
                    "after_state": {"internal_module_of": BOT_NAME,
                                    "legacy_record_preserved": True,
                                    "historical_task_ownership_preserved": True,
                                    "terminal_tasks_retained": historical_retained,
                                    "queued_tasks_reassigned": queued_reassigned},
                    "trace_id": f"mojtaba-merge-{old.pk}",
                },
            )

        self.stdout.write(self.style.SUCCESS(
            "Mojtaba.bot.ai is the sole economic/factory executor; "
            "legacy worker rows retained inactive for audit."
        ))
