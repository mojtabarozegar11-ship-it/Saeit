from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import BaseCommand


LOCK_KEY = "economic-master-cycle-lock"
LOCK_SECONDS = 55


class Command(BaseCommand):
    help = "Run one autonomous economic cycle: plan one concrete task, then execute it."

    def handle(self, *args, **options):
        if not cache.add(LOCK_KEY, "1", timeout=LOCK_SECONDS):
            self.stdout.write("SKIP: economic cycle already running.")
            return
        try:
            call_command("online_income_cycle")
            call_command("economic_worker", limit=1)
            self.stdout.write(self.style.SUCCESS("ECONOMIC_CYCLE_FINISHED"))
        finally:
            cache.delete(LOCK_KEY)
