from django.core.management.base import BaseCommand
from core.knowledge_agent import queue_cycle


class Command(BaseCommand):
    help = "Queue the next planned Knowledge Content Director cycle."

    def handle(self, *args, **options):
        run = queue_cycle()
        if run is None:
            self.stdout.write(self.style.SUCCESS("KNOWLEDGE_AGENT: library complete"))
            return
        self.stdout.write(self.style.SUCCESS(f"KNOWLEDGE_AGENT: queued run={run.pk} book={run.book.code}"))
