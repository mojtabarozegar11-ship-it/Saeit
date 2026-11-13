"""Consume private market research as a task of Mojtaba.bot.ai, never trade."""
from django.core.management.base import BaseCommand, CommandError

from core.mojtrade_bridge import MojTradeBridgeError, ingest_private_observation
from core.task_runtime import TaskExecutionError


class Command(BaseCommand):
    help = (
        "Ingest one existing MojTrade private market observation as canonical "
        "research evidence. Requires MOJTRADE_PRIVATE_DIR; no broker or orders."
    )

    def handle(self, *args, **options):
        try:
            task, created = ingest_private_observation()
        except (MojTradeBridgeError, TaskExecutionError) as exc:
            # Only fixed, non-sensitive validation reasons reach operator logs.
            raise CommandError(f"MOJTRADE_CANONICAL_INGEST_REJECTED: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(
            f"MOJTRADE_CANONICAL_RESEARCH task={task.pk} "
            f"new_receipt={int(created)} owner=mojtaba-bot-ai "
            "orders=0 broker_connected=false execution=disabled "
            "revenue_not_verified=true"
        ))
