from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db.models import F
from core.autonomous_brain import AutonomousBrain
from core.models import AgentTask
from core.economic_tool_pack import build_economic_gateway
from core.worker_runner import WorkerRunner
from core.unified_bot_identity import BOT_CODE, non_factory_task_scope

class Command(BaseCommand):
    help = "Autonomous observe-decide-execute-verify-replan loop."

    def add_arguments(self, parser):
        parser.add_argument("--max-steps", type=int, default=20)

    def handle(self,*args,**opts):
        brain=AutonomousBrain()
        gateway = build_economic_gateway()
        supported = frozenset(
            code for code, spec in gateway.describe().items()
            if spec.get("enabled", False)
            and (code.startswith("income_") or code == "master_self_improvement")
        )
        if not supported:
            self.stdout.write("AUTO_BLOCKED_NO_REGISTERED_TOOLS")
            return
        runner = None
        requested_steps=max(1, opts["max_steps"])
        steps=min(20, requested_steps)
        if requested_steps>steps:
            self.stdout.write(f"AUTO_SERIAL_STEP_CAP requested={requested_steps} applied={steps}")
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
                prereq=brain.prerequisite_from_error(exc)
                self.stdout.write(f"AUTO_REPLAN failed_task={active.pk} reason={exc} prerequisite={prereq or 'unknown'}")
                if not prereq:
                    return
                # Failed task is already safely requeued by WorkerRunner when retries remain.
                # Cancel it as superseded so the inferred prerequisite can run first.
                active.refresh_from_db()
                if active.status=="queued":
                    active.status="cancelled"
                    active.output_data={**(active.output_data or {}),"replanned_to":prereq,"blocker":str(exc)[:1000]}
                    active.save(update_fields=["status","output_data","updated_at"])
                agent=active.agent
                cap=agent.capabilities.filter(code=prereq,active=True).first()
                if not cap:
                    self.stdout.write(f"AUTO_BLOCKED missing_capability={prereq}"); return
                AgentTask.objects.create(agent=agent,action_type=prereq,capability_code=prereq,
                    risk_snapshot=cap.risk_level,input_data={"objective":agent.mission,"replanned_from":active.pk,
                    "reason":str(exc)[:1000]},status="queued")
                continue

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
