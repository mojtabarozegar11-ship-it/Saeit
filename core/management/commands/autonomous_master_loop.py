from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db.models import F
from core.models import AgentTask
from core.economic_tool_pack import build_economic_gateway
from core.worker_runner import WorkerRunner
from core.unified_bot_identity import BOT_CODE, non_factory_task_scope

class Command(BaseCommand):
    help = "Autonomous observe-decide-execute-verify-replan loop."

    def add_arguments(self, parser):
        parser.add_argument("--max-steps", type=int, default=20)

    def handle(self,*args,**opts):
        gateway = build_economic_gateway()
        supported = frozenset(
            code for code, spec in gateway.describe().items()
            if spec.get("enabled", False)
            and (code.startswith("income_") or code in {
                "master_self_improvement", "business_portfolio_review",
            })
        )
        if not supported:
            self.stdout.write("AUTO_BLOCKED_NO_REGISTERED_TOOLS")
            return
        runner = None
        requested_steps = opts["max_steps"]
        if not 1 <= requested_steps <= 20:
            raise ValueError("max-steps must be 1..20")
        steps = requested_steps
        for step in range(steps):
            in_flight = AgentTask.objects.filter(
                agent__code=BOT_CODE, agent__active=True, status="running"
            ).order_by("updated_at", "pk").first()
            if in_flight:
                self.stdout.write(
                    f"AUTO_WAIT_RUNNING task={in_flight.pk} "
                    "prevents_parallel_execution=true revenue_not_assessed=true"
                )
                return
            # Unreconciled tasks may already have caused real side effects.
            blocked = AgentTask.objects.filter(
                agent__code=BOT_CODE, agent__active=True, status="blocked"
            ).order_by("pk").first()
            if blocked:
                self.stdout.write(
                    f"AUTO_STOP_UNRECONCILED task={blocked.pk} "
                    "automatic_replay_allowed=false"
                )
                return
            active=self._next_eligible_task(supported)
            if not active:
                call_command("online_income_cycle")
                active=self._next_eligible_task(supported)
            if not active:
                unsupported = AgentTask.objects.filter(
                    agent__code=BOT_CODE, agent__active=True, status="queued",
                ).filter(non_factory_task_scope()).exclude(
                    capability_code__in=supported,
                    action_type=F("capability_code"),
                ).order_by("created_at", "pk").first()
                if unsupported:
                    self.stdout.write(
                        f"AUTO_BLOCKED_UNSUPPORTED_TASK task={unsupported.pk} "
                        f"capability={unsupported.capability_code} requires_review=true"
                    )
                    return
                self.stdout.write("AUTONOMOUS_IDLE"); return
            try:
                if runner is None:
                    runner = WorkerRunner(gateway)
                done=runner.run(active.pk)
                self.stdout.write(self.style.SUCCESS(
                    f"AUTO step={step+1} task={done.pk} action={done.action_type} "
                    f"internal_effect_verified={bool(done.output_data.get('verified_effect'))} "
                    f"revenue_not_assessed=true"
                ))
            except Exception as exc:
                # The handler may have made an irreversible effect before
                # raising. Never auto-enqueue an inferred prerequisite.
                active.refresh_from_db()
                self.stdout.write(
                    f"AUTO_STOP_RECONCILIATION task={active.pk} "
                    f"status={active.status} error_type={type(exc).__name__} "
                    "new_tasks_created=0 automatic_replay_allowed=false"
                )
                return

            # Stop when progress reaches an external-world boundary rather than
            # pretending an internal artifact equals a sale.
            done.refresh_from_db()
            if done.output_data.get("verified_effect") is not True:
                self.stdout.write(
                    f"AUTO_UNVERIFIED_STOP task={done.pk} action={done.action_type} requires_review=true"
                )
                return
            if done.action_type=="income_growth_experiment":
                self.stdout.write("AUTO_EXTERNAL_BOUNDARY growth experiment prepared; real acquisition requires an authorized external channel.")
                return

    @staticmethod
    def _next_eligible_task(supported):
        return AgentTask.objects.filter(
            agent__code=BOT_CODE, agent__active=True, status="queued",
            capability_code__in=supported,
            action_type=F("capability_code"),
        ).order_by("created_at", "pk").first()
