"""Compatibility entry point for the single, bounded economic worker.

The autonomous scheduler still invokes ``economic_worker``. Preserve that
public CLI but never maintain a competing dispatcher with different limits.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Execute up to 20 queued tasks through the single controlled economic worker."

    def add_arguments(self, parser):
        parser.add_argument("--task-id", type=int)
        parser.add_argument("--limit", type=int, default=1)

    def handle(self, *args, **options):
        call_command(
            "run_economic_worker",
            task_id=options["task_id"],
            limit=options["limit"],
            stdout=self.stdout,
            stderr=self.stderr,
        )
