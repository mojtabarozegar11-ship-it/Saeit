"""Bounded compatibility entrypoint for the existing VPS factory specialists."""

import os

from django.core.management.base import BaseCommand, CommandError

from core.factory_agent_runtime import FactoryAgentRuntime
from core.factory_tool_pack import build_factory_gateway
from core.factory_worker_compat import FactoryWorkerCompatibility
from core.models import AgentTask


class Command(BaseCommand):
    help = "Resume one explicitly selected, existing factory validation task."

    def add_arguments(self, parser):
        parser.add_argument("--task-id", type=int)
        parser.add_argument("--product-id", type=int)
        parser.add_argument("--payload-json", default="")
        parser.add_argument("--result-json", default="")

    def handle(self, *args, **opts):
        if opts.get("payload_json") or opts.get("result_json"):
            raise CommandError("Factory input planning and external agent results are disabled")
        task_id = opts.get("task_id")
        if not task_id:
            self.stdout.write("FACTORY_WAIT explicit_task_id_required")
            return
        task = AgentTask.objects.filter(pk=task_id, status="queued").first()
        if not task:
            raise CommandError("The requested factory task is not queued")
        if opts.get("product_id") and task.product_id != opts["product_id"]:
            raise CommandError("The selected factory Product differs from the task")
        # A disabled paid provider is a hard prerequisite; task-level cost is
        # separately checked by the compatibility worker before completion.
        if (os.environ.get("MOJ_PAID_LLM_ENABLED", "0").strip().lower()
                not in {"", "0", "false", "no"}):
            raise CommandError("Paid LLM execution is not permitted")
        try:
            result = FactoryWorkerCompatibility(
                build_factory_gateway(), FactoryAgentRuntime()
            ).run(task_id)
        except Exception as exc:
            task.refresh_from_db(fields=["status"])
            self.stdout.write(
                f"FACTORY_WAIT task={task.pk} status={task.status} reason={str(exc)[:250]}"
            )
            return
        self.stdout.write(self.style.SUCCESS(
            f"FACTORY_DONE task={result.pk} action={result.action_type} verified=True"
        ))
