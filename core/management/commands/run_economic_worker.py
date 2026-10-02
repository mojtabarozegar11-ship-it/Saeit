from django.core.management.base import BaseCommand, CommandError

from core.economic_tool_pack import build_economic_gateway
from core.models import AgentTask
from core.worker_runner import WorkerRunner


class Command(BaseCommand):
    help = "Execute one queued task for the single Economic Master Agent through real registered tools."

    def handle(self, *args, **options):
        task = AgentTask.objects.filter(
            agent__code="economic-master-agent",
            agent__active=True,
            status="queued",
            capability_code__startswith="income_",
        ).order_by("created_at").first()
        if not task:
            self.stdout.write("IDLE: no queued economic task.")
            return

        gateway = build_economic_gateway()
        if task.capability_code not in gateway.describe():
            raise CommandError(
                f"No concrete tool is registered for {task.capability_code}; task {task.pk} was not falsely completed."
            )

        try:
            completed = WorkerRunner(gateway).run(task.pk)
        except Exception as exc:
            raise CommandError(f"Task {task.pk} execution failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(
            f"EXECUTED task {completed.pk}: {completed.output_data.get('action_performed', '')}"
        ))
