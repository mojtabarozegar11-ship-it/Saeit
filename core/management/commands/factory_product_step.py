import json

from django.core.management.base import BaseCommand, CommandError
from core.autonomous_brain import AutonomousBrain
from core.factory_tool_pack import build_factory_gateway
from core.models import AgentTask
from core.worker_runner import WorkerRunner

class Command(BaseCommand):
    help="Execute one queued Product Factory task through the audited worker gateway."
    def add_arguments(self,parser):
        parser.add_argument("--task-id",type=int)
        parser.add_argument("--product-id",type=int)
        parser.add_argument("--payload-json",default="")
    def handle(self,*args,**opts):
        qs=AgentTask.objects.filter(action_type__startswith="product_",status="queued")
        task=qs.filter(pk=opts["task_id"]).first() if opts.get("task_id") else qs.order_by("created_at").first()
        if opts.get("task_id") and not task:
            raise CommandError("The requested task is not a queued Product Factory task.")
        if not task and opts.get("payload_json"):
            try:
                payload=json.loads(opts["payload_json"])
            except json.JSONDecodeError as exc:
                raise CommandError("--payload-json must be a valid JSON object.") from exc
            if not isinstance(payload,dict):
                raise CommandError("--payload-json must be a JSON object.")
            try:
                task=AutonomousBrain().plan_product_factory_step(
                    payload=payload, product_id=opts.get("product_id")
                )
            except RuntimeError as exc:
                raise CommandError(str(exc)) from exc
        if not task:
            self.stdout.write("FACTORY_IDLE"); return
        if task.status != "queued":
            self.stdout.write(f"FACTORY_WAIT task={task.pk} status={task.status}")
            return
        done=WorkerRunner(build_factory_gateway()).run(task.pk)
        self.stdout.write(self.style.SUCCESS(f"FACTORY_DONE task={done.pk} action={done.action_type} verified={done.output_data.get('verified_effect')}"))
