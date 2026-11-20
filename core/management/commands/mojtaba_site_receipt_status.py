"""Read-only proof of two distinct live public-monitor AuditLog receipts."""
import json

from django.core.management.base import BaseCommand

from core.mojtaba_site_receipts import inspect_public_monitor_continuity


class Command(BaseCommand):
    help = "Read persisted site public-monitor receipts; no private site or VPS access."

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(
            inspect_public_monitor_continuity(),
            ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ))
