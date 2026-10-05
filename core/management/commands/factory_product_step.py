from django.core.management.base import BaseCommand
from core.factory_tool_pack import build_factory_gateway
from core.models import AgentTask
from core.worker_runner import WorkerRunner

class Command(BaseCommand):
    help="Execute one queued Product Factory task through the audited worker gateway."
    def add_arguments(self,parser):
        parser.add_argument("--task-id",type=int)
    def handle(self,*args,**opts):
        qs=AgentTask.objects.filter(agent__code="factory-master-agent",status="queued")
        task=qs.filter(pk=opts["task_id"]).first() if opts.get("task_id") else qs.order_by("created_at").first()
        if not task:
            self.stdout.write("FACTORY_IDLE"); return
        done=WorkerRunner(build_factory_gateway()).run(task.pk)
        self.stdout.write(self.style.SUCCESS(f"FACTORY_DONE task={done.pk} action={done.action_type} verified={done.output_data.get('verified_effect')}"))
