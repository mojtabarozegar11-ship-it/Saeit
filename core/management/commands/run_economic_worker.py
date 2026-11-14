from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from core.economic_tool_pack import build_economic_gateway
from core.management.commands.autonomous_master_loop import registered_economic_tools
from core.models import AgentTask
from core.worker_runner import WorkerRunner


class Command(BaseCommand):
    help = "Execute queued tasks for the single Economic Master Agent through real registered tools."

    MAX_DRAIN_TASKS = 20

    def add_arguments(self, parser):
        parser.add_argument("--drain", action="store_true")
        parser.add_argument("--limit", type=int, default=1)
        parser.add_argument("--task-id", type=int)

    def handle(self, *args, **options):
        requested_limit = options["limit"]
        if not 1 <= requested_limit <= self.MAX_DRAIN_TASKS:
            raise CommandError(f"limit must be between 1 and {self.MAX_DRAIN_TASKS}")
        if options["drain"] and (requested_limit != 1 or options["task_id"] is not None):
            raise CommandError("--drain cannot be combined with --limit or --task-id")
        if options["task_id"] is not None and requested_limit != 1:
            raise CommandError("--task-id runs one explicitly selected task")
        if options["task_id"] is not None and options["task_id"] <= 0:
            raise CommandError("--task-id must be positive")
        limit = self.MAX_DRAIN_TASKS if options["drain"] else requested_limit
        executed = 0
        attempted_ids = []
        gateway = build_economic_gateway()
        # Share the strict allowlist with the autonomous master loop.
        # A missing or non-boolean enabled flag is never permission to execute.
        supported = registered_economic_tools(gateway)
        runner = None
        for _ in range(limit):
            # Never retry the same queued identity within this invocation.
            # A failed or re-queued task is left for the normal retry policy.
            task_query = (
                AgentTask.objects.filter(
                    agent__code="economic-master-agent",
                    agent__active=True,
                    status="queued",
                    capability_code__in=supported,
                    action_type=F("capability_code"),
                )
                .exclude(pk__in=attempted_ids)
            )
            if options["task_id"] is not None:
                task_query = task_query.filter(pk=options["task_id"])
            task = task_query.order_by("created_at", "pk").first()
            if not task:
                if options["task_id"] is not None:
                    raise CommandError("Explicit task is not queued with a matching registered economic tool")
                if executed == 0:
                    unknown = AgentTask.objects.filter(
                        agent__code="economic-master-agent", agent__active=True, status="queued",
                    ).exclude(
                        capability_code__in=supported, action_type=F("capability_code"),
                    ).order_by("created_at", "pk").first()
                    if unknown:
                        self.stdout.write(
                            f"BLOCKED_UNSUPPORTED: task={unknown.pk} "
                            "requires_review=true"
                        )
                    else:
                        self.stdout.write("IDLE: no queued economic task.")
                break
            attempted_ids.append(task.pk)
            if runner is None:
                runner = WorkerRunner(gateway)

            try:
                completed = runner.run(task.pk)
            except Exception as exc:
                # Provider/tool exceptions may contain credentials, private
                # inputs or customer data. Suppress chained tracebacks as
                # well as the direct CLI message to avoid accidental leakage.
                raise CommandError(
                    f"Task {task.pk} execution failed: worker_execution_error"
                ) from None
            if getattr(completed, "pk", None) != task.pk:
                raise CommandError(f"Task {task.pk} rejected: worker_task_identity_mismatch")
            if getattr(completed, "status", None) != "completed":
                raise CommandError(f"Task {task.pk} rejected: worker_result_not_completed")
            if getattr(completed, "action_type", task.action_type) != task.action_type:
                raise CommandError(f"Task {task.pk} rejected: worker_action_mismatch")
            output = completed.output_data if isinstance(completed.output_data, dict) else {}
            verified_effect = output.get("verified_effect") is True
            if not verified_effect:
                # A database status of completed is NOT proof of a real effect.
                # Stop draining rather than reporting fake successful work.
                self.stdout.write(
                    f"EXECUTED_UNVERIFIED task={task.pk} "
                    "internal_effect_verified=0 revenue_not_assessed=true "
                    "requires_review=true"
                )
                break
            executed += 1
            self.stdout.write(self.style.SUCCESS(
                f"EXECUTED task={task.pk} action={task.action_type} status=completed "
                "internal_effect_verified=1 revenue_not_assessed=true"
            ))
        if options["drain"]:
            self.stdout.write(f"DRAIN_SUMMARY completed={executed} limit={self.MAX_DRAIN_TASKS}")
