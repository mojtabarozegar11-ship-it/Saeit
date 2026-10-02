from django.core.management.base import BaseCommand, CommandError
from core.models import AgentTask
from core.tool_gateway import ToolGateway, ToolSpec
from core.worker_runner import WorkerRunner
from core import economic_tools

TOOLS = {
    "income_market_research": economic_tools.market_research,
    "income_opportunity_score": economic_tools.opportunity_score,
    "income_offer_design": economic_tools.offer_design,
    "income_mvp_build": economic_tools.mvp_build,
    "income_growth_experiment": economic_tools.growth_experiment,
    "income_revenue_verify": economic_tools.revenue_verify,
    "income_profit_optimize": economic_tools.profit_optimize,
}

def gateway():
    return ToolGateway([
        ToolSpec(code=code, handler=handler, risk="low")
        for code, handler in TOOLS.items()
    ])

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
        runner = WorkerRunner(gateway())
        for task_id in ids:
            try:
                task = runner.run(task_id)
            except Exception as exc:
                raise CommandError(f"Task {task_id} failed: {exc}") from exc
            self.stdout.write(self.style.SUCCESS(
                f"EXECUTED task={task.pk} action={task.action_type} status={task.status}"
            ))
