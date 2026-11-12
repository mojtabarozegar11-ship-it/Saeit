"""Record only corroborating DEMO history evidence in the canonical bot."""
from django.core.management.base import BaseCommand, CommandError

from core.mojtrade_statement_bridge import (
    DemoStatementBridgeError, ingest_demo_statement_crosscheck,
)
from core.mojtrade_demo_evidence_bridge import DemoEvidenceBridgeError
from core.task_runtime import TaskExecutionError


class Command(BaseCommand):
    help = (
        "Match private cTrader demo closed-deal log against a separately "
        "normalized demo statement. No broker access, orders or revenue claim."
    )

    def handle(self, *args, **options):
        try:
            task, created = ingest_demo_statement_crosscheck()
        except (DemoStatementBridgeError, DemoEvidenceBridgeError,
                TaskExecutionError) as exc:
            raise CommandError("MOJTRADE_STATEMENT_CROSSCHECK_BLOCKED: " + str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"MOJTRADE_STATEMENT_CROSSCHECK task={task.pk} new_receipt={int(created)} "
            "owner=mojtaba-bot-ai matched_two_unverified_demo_exports=true "
            "broker_statement_authenticated=false real_revenue_verified=false orders=0"
        ))
