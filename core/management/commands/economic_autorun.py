from io import StringIO

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
            plan_output = StringIO()
            worker_output = StringIO()
            call_command("online_income_cycle", stdout=plan_output)
            call_command("economic_worker", limit=1, stdout=worker_output)
            self.stdout.write(plan_output.getvalue().strip())
            self.stdout.write(worker_output.getvalue().strip())
            if "EXECUTED task=" in worker_output.getvalue():
                self.stdout.write("ECONOMIC_INTERNAL_TASK_EXECUTED revenue_not_assessed")
            else:
                self.stdout.write("ECONOMIC_NO_TASK_EXECUTED")
        finally:
            cache.delete(LOCK_KEY)
