"""Read-only sales reconciliation for mojtaba.bot.ai; no gateway or host write."""
import json
from django.core.management.base import BaseCommand
from core.revenue_evidence_gate import revenue_evidence_snapshot


class Command(BaseCommand):
    help = "Inspect 30 days of internal sales evidence without asserting settled cash."

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(
            revenue_evidence_snapshot(), ensure_ascii=False, sort_keys=True
        ))
