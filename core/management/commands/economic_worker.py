from django.core.management.base import BaseCommand, CommandError
from core.models import AgentTask
from core.worker_runner import WorkerRunner
from core.economic_tool_pack import build_economic_gateway


class Command(BaseCommand):
    help = "Execute queued economic master-agent tasks through the controlled gateway."

    def add_arguments(self, parser):
        parser.add_argument("--task-id", type=int)
        parser.add_argument("--limit", type=int, default=1)

    def handle(self, *args, **options):
        qs = AgentTask.objects.filter(
            agent__code="economic-master-agent",
            capability_code__startswith="income_",
            status="queued",
        ).order_by("created_at")
        if options["task_id"]:
            qs = qs.filter(pk=options["task_id"])
        ids = list(qs.values_list("pk", flat=True)[:max(1, options["limit"])])
        if not ids:
            self.stdout.write("NO_QUEUED_ECONOMIC_TASK")
            return
        runner = WorkerRunner(build_economic_gateway())
        for task_id in ids:
            try:
                task = runner.run(task_id)
            except Exception as exc:
                raise CommandError(f"Task {task_id} failed: {exc}") from exc
            self.stdout.write(self.style.SUCCESS(
                f"EXECUTED task={task.pk} action={task.action_type} status={task.status}"
            ))
