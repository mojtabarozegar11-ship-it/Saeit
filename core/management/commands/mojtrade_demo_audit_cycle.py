"""Read one private cTrader DEMO history log into the canonical bot ledger."""
from django.core.management.base import BaseCommand, CommandError

from core.mojtrade_demo_evidence_bridge import (
    DemoEvidenceBridgeError, ingest_private_demo_evidence,
)
from core.task_runtime import TaskExecutionError


class Command(BaseCommand):
    help = (
        "Check closed demo trades and cost-inclusive broker-reported net PnL. "
        "No real trading, broker connection, publication or income verification."
    )

    def handle(self, *args, **options):
        try:
            task, new = ingest_private_demo_evidence()
        except (DemoEvidenceBridgeError, TaskExecutionError) as exc:
            raise CommandError(f"MOJTRADE_DEMO_EVIDENCE_BLOCKED: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(
            f"MOJTRADE_DEMO_AUDIT task={task.pk} new_receipt={int(new)} "
            "owner=mojtaba-bot-ai orders=0 broker_statement_reconciled=false "
            "real_revenue_verified=false"
        ))
