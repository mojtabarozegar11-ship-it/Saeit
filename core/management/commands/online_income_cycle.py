from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.autonomous_brain import AutonomousBrain
from core.models import Agent, AgentTask
from core.economic_tool_pack import build_economic_gateway
from core.task_runtime import TaskExecutionError, TaskRuntime

MASTER_AGENT_CODE = "economic-master-agent"

class Command(BaseCommand):
    help = "Let the master agent observe state and autonomously choose its next work."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--stale-after-seconds", type=int, default=900)

    @transaction.atomic
    def handle(self, *args, **options):
        if options["stale_after_seconds"] < 300:
            raise CommandError("stale-after-seconds must be at least 300")
        agent = Agent.objects.filter(code=MASTER_AGENT_CODE, active=True).first()
        if not agent:
            self.stderr.write("Missing active economic-master-agent.")
            return

        queued = AgentTask.objects.filter(agent=agent, status="queued").order_by("created_at").first()
        if queued:
            if queued.attempt_count >= queued.max_attempts:
                self.stdout.write(
                    f"BRAIN_BLOCKED_RETRY_EXHAUSTED task={queued.pk} requires_review=true"
                )
                return
            registered = build_economic_gateway().describe()
            capability = agent.capabilities.filter(
                code=queued.capability_code, active=True,
            ).exists()
            supported = (
                queued.action_type == queued.capability_code
                and queued.capability_code in registered
                and registered[queued.capability_code]["enabled"]
                and (queued.action_type.startswith("income_")
                     or queued.action_type == "master_self_improvement")
            )
            if not supported or not capability:
                self.stdout.write(
                    f"BRAIN_BLOCKED_UNROUTABLE task={queued.pk} requires_review=true"
                )
                return
            self.stdout.write(
                f"BRAIN_CONTINUE task={queued.pk} action={queued.action_type} status={queued.status}"
            )
            return

        running = AgentTask.objects.filter(agent=agent, status="running").order_by("updated_at").first()
        if running:
            if options["dry_run"]:
                self.stdout.write(f"BRAIN_RUNNING task={running.pk} dry_run=true")
                return
            try:
                recovered = TaskRuntime().recover_stale(
                    running.pk, stale_after_seconds=options["stale_after_seconds"]
                )
            except TaskExecutionError:
                self.stdout.write(f"BRAIN_RUNNING task={running.pk} awaiting_heartbeat_or_recovery")
                return
            self.stdout.write(f"BRAIN_RECOVERED task={recovered.pk} status={recovered.status}")
            return

        blocked = AgentTask.objects.filter(agent=agent, status="blocked").order_by("created_at").first()
        if blocked:
            # A blocked task may be awaiting owner authorization. Never silently
            # retry it, spawn duplicates, or report a successful autonomous step.
            self.stdout.write(f"BRAIN_BLOCKED task={blocked.pk} requires_review=true")
            return

        # Read-only dry-run must never take a row lock; it merely reports a
        # snapshot. Only the path that could create work needs serialization.
        # Stale-task recovery happens first to retain the worker lock order.
        if not options["dry_run"]:
            agent = Agent.objects.select_for_update().filter(pk=agent.pk, active=True).first()
            if agent is None:
                self.stderr.write("Economic master agent was deactivated during planning.")
                return
            if AgentTask.objects.filter(
                agent=agent, status__in=("queued", "running", "blocked")
            ).exists():
                self.stdout.write("BRAIN_RECHECK pending_task_created_concurrently")
                return

        decision = AutonomousBrain().decide()
        chosen = decision["chosen"]
        action = chosen["action"]
        if action == "continue_existing_work":
            self.stdout.write("BRAIN_CONTINUE")
            return
        if action.startswith("await_external_"):
            self.stdout.write(
                f"BRAIN_EXTERNAL_BOUNDARY action={action} reason={chosen['reason']}"
            )
            return
        capability = agent.capabilities.filter(code=action, active=True).first()
        if not capability:
            self.stderr.write(f"BRAIN_BLOCKED missing capability={action}")
            return
        if options["dry_run"]:
            self.stdout.write(f"BRAIN_DECISION action={action} reason={chosen['reason']} score={chosen['score']}")
            return

        task = AgentTask.objects.create(
            agent=agent,
            action_type=action,
            capability_code=action,
            risk_snapshot=capability.risk_level,
            input_data={
                **({"inquiry_id": decision["state"]["new_inbound_inquiry_id"]}
                   if action == "income_inbound_lead_review" else {}),
                "objective": agent.mission,
                "brain_decision": decision,
                "execution_contract": {
                    "must_execute_not_just_report": True,
                    "success_requires_verified_effect": True,
                    "reobserve_after_execution": True,
                    "production_limits": {
                        "max_new_products_per_cycle": 1,
                        "max_concurrent_master_tasks": 1,
                        "parallel_product_builds": False,
                        "automatic_volume_expansion": False,
                        "private_only_until_qc1000_and_rights_review": True,
                    },
                },
            },
            status="queued",
        )
        self.stdout.write(self.style.SUCCESS(
            f"BRAIN_DECISION task={task.pk} action={action} score={chosen['score']} reason={chosen['reason']}"
        ))
