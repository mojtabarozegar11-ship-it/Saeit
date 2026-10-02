from django.core.management.base import BaseCommand
from django.db import transaction
from core.autonomous_brain import AutonomousBrain
from core.models import Agent, AgentTask

MASTER_AGENT_CODE = "economic-master-agent"

class Command(BaseCommand):
    help = "Let the master agent observe state and autonomously choose its next work."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        agent = Agent.objects.filter(code=MASTER_AGENT_CODE, active=True).first()
        if not agent:
            self.stderr.write("Missing active economic-master-agent.")
            return

        active = AgentTask.objects.filter(
            agent=agent, status__in=("queued","running","blocked")
        ).order_by("created_at").first()
        if active:
            self.stdout.write(
                f"BRAIN_CONTINUE task={active.pk} action={active.action_type} status={active.status}"
            )
            return

        decision = AutonomousBrain().decide()
        chosen = decision["chosen"]
        action = chosen["action"]
        if action == "continue_existing_work":
            self.stdout.write("BRAIN_CONTINUE")
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
                "objective": agent.mission,
                "brain_decision": decision,
                "execution_contract": {
                    "must_execute_not_just_report": True,
                    "success_requires_verified_effect": True,
                    "reobserve_after_execution": True,
                },
            },
            status="queued",
        )
        self.stdout.write(self.style.SUCCESS(
            f"BRAIN_DECISION task={task.pk} action={action} score={chosen['score']} reason={chosen['reason']}"
        ))
