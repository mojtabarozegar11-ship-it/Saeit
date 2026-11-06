from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from core.economic_tool_pack import build_economic_gateway
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
        supported = frozenset(
            code for code, spec in gateway.describe().items()
            if spec.get("enabled", True)
            and (code.startswith("income_") or code == "master_self_improvement")
        )
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
                            f"capability={unknown.capability_code} requires_review=true"
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
                raise CommandError(f"Task {task.pk} execution failed: {exc}") from exc
            if completed.status != "completed":
                raise CommandError(f"Task {task.pk} was not completed; status={completed.status}")
            executed += 1
            output = completed.output_data if isinstance(completed.output_data, dict) else {}
            verified_effect = output.get("verified_effect") is True
            self.stdout.write(self.style.SUCCESS(
                f"EXECUTED task={completed.pk} action={task.action_type} status={completed.status} "
                f"internal_effect_verified={int(verified_effect)} revenue_not_assessed=true"
            ))
            # A completed task can still have no independently checked internal
            # effect. Do not drain the rest of the queue after that signal: it
            # needs human review rather than another batch of claimed progress.
            if not verified_effect:
                self.stdout.write(
                    f"DRAIN_PAUSED_UNVERIFIED task={completed.pk} requires_review=true"
                )
                break
            # Acquisition beyond the private growth hypothesis is an external
            # authorization boundary, even when the hypothesis was recorded.
            if task.action_type == "income_growth_experiment":
                self.stdout.write(
                    "DRAIN_EXTERNAL_BOUNDARY growth experiment prepared; "
                    "customer acquisition requires an authorized channel."
                )
                break
        if options["drain"]:
            self.stdout.write(f"DRAIN_SUMMARY completed={executed} limit={self.MAX_DRAIN_TASKS}")
