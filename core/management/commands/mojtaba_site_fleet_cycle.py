"""One explicit operator entrypoint; never creates another Agent."""
import json
from django.core.management.base import BaseCommand, CommandError
from core.mojtaba_site_dispatch import execute_site_cycle
from core.mojtaba_site_fleet import inventory, SiteFleetError

class Command(BaseCommand):
    help = "Mojtaba.bot.ai site inventory or durably claimed public observation"
    def add_arguments(self, parser):
        parser.add_argument("--observe-public", action="store_true")
        parser.add_argument("--cycle-id")
    def handle(self, *args, **options):
        observe, cycle = options["observe_public"], options.get("cycle_id")
        if observe != bool(cycle):
            raise CommandError("OBSERVATION_REQUIRES_EXPLICIT_CYCLE_ID")
        try:
            result = execute_site_cycle(cycle) if observe else inventory()
        except SiteFleetError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
