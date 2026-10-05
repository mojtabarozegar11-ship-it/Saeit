import json
from django.core.management.base import BaseCommand
from core.staging_readiness import StagingPreflight

class Command(BaseCommand):
    help = "Machine-readable fail-closed readiness check for isolated real staging."

    def handle(self, *args, **options):
        result = StagingPreflight().evaluate().as_dict()
        self.stdout.write(json.dumps(result, sort_keys=True))
