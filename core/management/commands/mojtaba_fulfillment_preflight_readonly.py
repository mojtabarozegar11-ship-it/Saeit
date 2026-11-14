"""Read-only delivery preflight: zero outgoing mail, downloads, grants, or writes."""
import json
from django.core.management.base import BaseCommand

from core.fulfillment_preflight import fulfillment_preflight_snapshot


class Command(BaseCommand):
    help = "Anonymized buyer fulfillment preflight, no delivery side effects."

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(
            fulfillment_preflight_snapshot(), ensure_ascii=False, sort_keys=True,
        ))
