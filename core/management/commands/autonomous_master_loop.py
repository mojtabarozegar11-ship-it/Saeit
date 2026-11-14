"""Single economic bot's bounded execute-and-replan loop.

An internal task receipt is not external revenue, delivery or deployment.
All real financial actions remain controlled by TaskRuntime/ToolGateway grants.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F

from core.autonomous_brain import AutonomousBrain
from core.economic_tool_pack import build_economic_gateway
from core.models import AgentTask
from core.worker_runner import WorkerRunner


MAX_STEPS = 20
MASTER_AGENT_CODE = "economic-master-agent"
REPLAN_PREREQUISITES = frozenset({
    "income_mvp_build", "income_offer_design",
})


def registered_economic_tools(gateway):
    """Only registered, enabled, economic tool handlers can be executed."""
    specs = gateway.describe()
    if not isinstance(specs, dict):
        raise CommandError("Economic gateway registry is invalid")
    return frozenset(
        code for code, spec in specs.items()
        if isinstance(code, str)
        and isinstance(spec, dict)
        and spec.get("enabled", False) is True
        and (code.startswith("income_") or code == "master_self_improvement")
    )


def _failure_classification(exc):
    """Public output must not include raw tool/provider/user error strings."""
    if isinstance(exc, (ValueError, CommandError)):
        return "validation_or_policy"
    return "worker_execution"


class Command(BaseCommand):
    help = (
        "Execute up to 20 bounded, registered economic tasks of the "
        "existing master bot; internal effects are not revenue receipts."
    )

    def add_arguments(self, parser):
        parser.add_argument("--max-steps", type=int, default=MAX_STEPS)

    def handle(self, *args, **opts):
        requested_steps = opts["max_steps"]
        if type(requested_steps) is not int or requested_steps < 1:
            raise CommandError("--max-steps must be a positive integer")
        steps = min(MAX_STEPS, requested_steps)
        if requested_steps > steps:
            self.stdout.write(
                f"AUTO_SERIAL_STEP_CAP requested={requested_steps} applied={steps}"
            )

        brain = AutonomousBrain()
        gateway = build_economic_gateway()
        supported = registered_economic_tools(gateway)
        if not supported:
            self.stdout.write("AUTO_BLOCKED_NO_REGISTERED_TOOLS")
            return
        runner = None
        for step in range(steps):
            active = self._next_eligible_task(supported)
            if not active:
                # Reuse the existing planner, with the same caller-visible log;
                # do not create another bot or competing queue implementation.
                call_command(
                    "online_income_cycle", stdout=self.stdout, stderr=self.stderr
                )
                active = self._next_eligible_task(supported)
            if not active:
                unsupported = (
                    AgentTask.objects.filter(
                        agent__code=MASTER_AGENT_CODE,
                        agent__active=True, status="queued",
                    )
                    .exclude(
                        capability_code__in=supported,
                        action_type=F("capability_code"),
                    )
                    .order_by("created_at", "pk").first()
                )
                if unsupported:
                    # Only the internal task identifier escapes; action strings
                    # may contain unsafe or customer-provided content.
                    self.stdout.write(
                        f"AUTO_BLOCKED_UNSUPPORTED_TASK task={unsupported.pk} "
                        "requires_review=true"
                    )
                else:
                    self.stdout.write("AUTONOMOUS_IDLE")
                return

            try:
                if runner is None:
                    runner = WorkerRunner(gateway)
                done = runner.run(active.pk)
            except Exception as exc:
                prerequisite = brain.prerequisite_from_error(exc)
                safe_code = _failure_classification(exc)
                self.stdout.write(
                    f"AUTO_REPLAN failed_task={active.pk} reason_code={safe_code} "
                    f"prerequisite={prerequisite if prerequisite in REPLAN_PREREQUISITES else 'unknown'}"
                )
                if prerequisite not in REPLAN_PREREQUISITES:
                    return
                if prerequisite not in supported:
                    self.stdout.write("AUTO_BLOCKED_PREREQUISITE_NOT_REGISTERED")
                    return
                result = self._replan_task(active.pk, prerequisite)
                self.stdout.write(f"AUTO_REPLAN_STATE={result}")
                if result not in ("created", "existing_prerequisite"):
                    return
                continue

            # Some test doubles do not implement status, but a real WorkerRunner
            # returns a persisted AgentTask. Never count an explicitly failed
            # or incorrect task as a completed autonomous step.
            if getattr(done, "pk", None) != active.pk:
                self.stdout.write("AUTO_TASK_IDENTITY_MISMATCH_STOP")
                return
            status = getattr(done, "status", "completed")
            if status != "completed":
                self.stdout.write("AUTO_INCOMPLETE_TASK_STOP")
                return
            output = getattr(done, "output_data", None)
            if not isinstance(output, dict):
                self.stdout.write("AUTO_INVALID_RECEIPT_STOP")
                return
            if getattr(done, "action_type", active.action_type) != active.action_type:
                self.stdout.write("AUTO_TASK_ACTION_MISMATCH_STOP")
                return

            # DB transaction completion is still only an internal result. A
            # truthful success line must indicate the verification boundary.
            verified = output.get("verified_effect") is True
            self.stdout.write(
                f"AUTO step={step + 1} task={done.pk} "
                f"action={active.action_type} internal_effect_verified={int(verified)} "
                "revenue_not_assessed=true"
            )
            if not verified:
                self.stdout.write(
                    f"AUTO_UNVERIFIED_STOP task={done.pk} "
                    f"action={active.action_type} requires_review=true"
                )
                return
            # Re-observe the same completed task after the handler; no second
            # autonomous agent, no automatic financial or external execution.
            done.refresh_from_db()
            if done.action_type == "income_growth_experiment":
                self.stdout.write(
                    "AUTO_EXTERNAL_BOUNDARY acquisition_requires_authorized_channel=true"
                )
                return

    @staticmethod
    @transaction.atomic
    def _replan_task(task_id, prerequisite):
        """Replace an already requeued failure atomically, without duplicates."""
        if prerequisite not in REPLAN_PREREQUISITES:
            return "unknown_prerequisite"
        row = (
            AgentTask.objects.select_for_update()
            .select_related("agent").filter(pk=task_id).first()
        )
        if row is None:
            return "task_disappeared"
        if not row.agent.active:
            return "inactive_agent"
        # Don't overwrite failed, cancelled, running, blocked or completed
        # transitions made by a concurrent actor or the retry policy.
        if row.status != "queued":
            return "task_not_queued"
        cap = row.agent.capabilities.filter(code=prerequisite, active=True).first()
        if cap is None:
            return "missing_capability"

        prior = AgentTask.objects.filter(
            agent=row.agent,
            action_type=prerequisite,
            capability_code=prerequisite,
            status__in=("queued", "running", "blocked"),
        ).exclude(pk=row.pk).exists()
        row.status = "cancelled"
        prior_output = row.output_data if isinstance(row.output_data, dict) else {}
        row.output_data = {
            **prior_output,
            "replanned_to": prerequisite,
            "replan_reason_code": "dependency_missing",
        }
        row.save(update_fields=["status", "output_data", "updated_at"])
        if prior:
            return "existing_prerequisite"
        AgentTask.objects.create(
            agent=row.agent,
            project=row.project,
            action_type=prerequisite,
            capability_code=prerequisite,
            risk_snapshot=cap.risk_level,
            input_data={
                "objective": row.agent.mission,
                "replanned_from": row.pk,
                "reason_code": "dependency_missing",
                "execution_contract": {
                    "must_execute_not_just_report": True,
                    "success_requires_verified_effect": True,
                },
            },
            status="queued",
        )
        return "created"

    @staticmethod
    def _next_eligible_task(supported):
        return (
            AgentTask.objects.filter(
                agent__code=MASTER_AGENT_CODE,
                agent__active=True,
                status="queued",
                capability_code__in=supported,
                action_type=F("capability_code"),
            )
            .order_by("created_at", "pk").first()
        )
