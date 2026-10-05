import json
import uuid
import time
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from core.autonomous_brain import AutonomousBrain
from core.economic_tool_pack import build_economic_gateway
from core.factory_agent_runtime import FactoryAgentRuntime
from core.factory_tool_pack import build_factory_gateway
from core.models import AgentTask, FactoryRun
from core.recovery_scheduler import RecoveryScheduler
from core.worker_runner import WorkerRunner


class Command(BaseCommand):
    help = "Resume the autonomous observe-decide-execute-verify-replan loop."

    def add_arguments(self, parser):
        parser.add_argument("--max-steps", type=int, default=20)
        parser.add_argument("--factory", action="store_true", help="Run or resume a Product Factory Run.")
        parser.add_argument("--goal", default="")
        parser.add_argument("--run-id", default="")
        parser.add_argument("--constraints-json", default="")

    def handle(self, *args, **opts):
        if opts["factory"]:
            return self.run_factory(opts)
        return self.run_economic(opts)

    def run_factory(self, opts):
        run_id = opts["run_id"] or uuid.uuid4().hex
        run = FactoryRun.objects.filter(run_id=run_id).first()
        goal = (opts["goal"] or (run.goal if run else "")).strip()
        if not goal:
            raise CommandError("--goal is required when starting a Factory Run.")
        if run and run.goal != goal:
            raise CommandError("A resumed Factory Run must retain its original goal.")
        if run and run.status != "active":
            self.stdout.write(f"FACTORY_BLOCKED run={run.run_id} status={run.status}")
            return
        try:
            constraints = json.loads(opts["constraints_json"]) if opts["constraints_json"] else (run.constraints if run else [])
        except json.JSONDecodeError as exc:
            raise CommandError("--constraints-json must be valid JSON.") from exc
        if not isinstance(constraints, (dict, list)):
            raise CommandError("--constraints-json must be a JSON object or list.")
        if not run:
            run = FactoryRun.objects.create(
                run_id=run_id, goal=goal, constraints=constraints,
                environment=str(getattr(settings, "FACTORY_ENVIRONMENT", "development")),
            )
        elif opts["constraints_json"] and run.constraints != constraints:
            raise CommandError("A resumed Factory Run must retain its original constraints.")
        self.stdout.write(f"FACTORY_RUN run={run_id}")
        brain = AutonomousBrain()
        executor = FactoryAgentRuntime()
        for step in range(max(1, opts["max_steps"])):
            run = FactoryRun.objects.get(run_id=run_id)
            task = run.tasks.filter(status="queued").filter(
                Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=timezone.now())
            ).order_by("created_at", "pk").first()
            if not task:
                delayed = run.tasks.filter(status="queued", next_retry_at__gt=timezone.now()).order_by("next_retry_at", "pk").first()
                if delayed:
                    wait_seconds = max(0.0, (delayed.next_retry_at - timezone.now()).total_seconds())
                    self.stdout.write(f"FACTORY_RETRY_WAIT run={run_id} task={delayed.pk} retry_at={delayed.next_retry_at}")
                    time.sleep(min(wait_seconds, 300.0))
                    continue
                active = run.tasks.filter(status="running").order_by("created_at", "pk").first()
                if active:
                    RecoveryScheduler().recover(limit=50, stale_after_seconds=900)
                    active.refresh_from_db()
                    if active.status == "running":
                        self.stdout.write(f"FACTORY_WAIT run={run_id} task={active.pk} status=running")
                        return
                    continue
                blocked = run.tasks.filter(status="blocked").order_by("created_at", "pk").first()
                if blocked:
                    run.status = "blocked"
                    run.save(update_fields=["status", "updated_at"])
                    self.stdout.write(f"FACTORY_BLOCKED run={run_id} task={blocked.pk} reason={(blocked.output_data or {}).get('error', '')}")
                    return
                failed = run.tasks.filter(status="failed").order_by("created_at", "pk").first()
                if failed:
                    run.status = "blocked"
                    run.save(update_fields=["status", "updated_at"])
                    self.stdout.write(f"FACTORY_BLOCKED run={run_id} task={failed.pk} reason={(failed.output_data or {}).get('error', '')}")
                    return
                try:
                    task = brain.plan_product_factory_step(
                        payload={"goal": run.goal, "constraints": run.constraints}, product_id=run.product_id, run_id=run.run_id
                    )
                except RuntimeError as exc:
                    self.stdout.write(f"FACTORY_REPLAN_BLOCKED run={run_id} reason={exc}")
                    return
            if task.status != "queued":
                self.stdout.write(f"FACTORY_WAIT run={run_id} task={task.pk} status={task.status}")
                return
            try:
                done = WorkerRunner(build_factory_gateway(), factory_executor=executor).run(task.pk)
            except Exception as exc:
                task.refresh_from_db()
                if task.status in ("failed", "blocked"):
                    run.status = "blocked"
                    run.save(update_fields=["status", "updated_at"])
                    self.stdout.write(f"FACTORY_BLOCKED run={run_id} task={task.pk} reason={str(exc)[:500]}")
                    return
                self.stdout.write(f"FACTORY_RETRY run={run_id} task={task.pk} next={task.next_retry_at} reason={str(exc)[:300]}")
                continue
            self.stdout.write(self.style.SUCCESS(
                f"FACTORY_STEP run={run_id} step={step + 1} task={done.pk} action={done.action_type} verified=True"
            ))
            if done.action_type == "product_launch_candidate":
                self.stdout.write(self.style.SUCCESS(
                    f"FACTORY_LAUNCH_CANDIDATE run={run_id} product={done.output_data.get('product_id')} published=False deployed=False"
                ))
                return
        self.stdout.write(f"FACTORY_PAUSED run={run_id} reason=max_steps; resume with --run-id {run_id}")

    def run_economic(self, opts):
        brain = AutonomousBrain()
        for step in range(max(1, opts["max_steps"])):
            active = AgentTask.objects.filter(agent__code="economic-master-agent", status="queued").order_by("created_at").first()
            if not active:
                call_command("online_income_cycle")
                active = AgentTask.objects.filter(agent__code="economic-master-agent", status="queued").order_by("created_at").first()
            if not active:
                self.stdout.write("AUTONOMOUS_IDLE")
                return
            try:
                done = WorkerRunner(build_economic_gateway()).run(active.pk)
                self.stdout.write(self.style.SUCCESS(
                    f"AUTO step={step + 1} task={done.pk} action={done.action_type} verified={done.output_data.get('verified_effect')}"
                ))
            except Exception as exc:
                prereq = brain.prerequisite_from_error(exc)
                self.stdout.write(f"AUTO_REPLAN failed_task={active.pk} reason={exc} prerequisite={prereq or 'unknown'}")
                if not prereq:
                    return
                active.refresh_from_db()
                if active.status == "queued":
                    active.status = "cancelled"
                    active.output_data = {**(active.output_data or {}), "replanned_to": prereq, "blocker": str(exc)[:1000]}
                    active.save(update_fields=["status", "output_data", "updated_at"])
                agent = active.agent
                cap = agent.capabilities.filter(code=prereq, active=True).first()
                if not cap:
                    self.stdout.write(f"AUTO_BLOCKED missing_capability={prereq}")
                    return
                AgentTask.objects.create(
                    agent=agent, action_type=prereq, capability_code=prereq,
                    risk_snapshot=cap.risk_level,
                    input_data={"objective": agent.mission, "replanned_from": active.pk, "reason": str(exc)[:1000]},
                    status="queued",
                )
                continue
            done.refresh_from_db()
            if done.action_type == "income_growth_experiment":
                self.stdout.write("AUTO_EXTERNAL_BOUNDARY growth experiment prepared; real acquisition requires an authorized external channel.")
                return
