import json

from django.core.management.base import BaseCommand, CommandError

from core.recovery_scheduler import RecoveryScheduler


class Command(BaseCommand):
    help = "Recover stale running agent tasks in a bounded, read/write-safe pass."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--stale-after", type=int, default=900)

    def handle(self, *args, **options):
        try:
            summary = RecoveryScheduler().recover(
                limit=options["limit"],
                stale_after_seconds=options["stale_after"],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        payload = {
            "scanned": summary.scanned,
            "recovered": summary.recovered,
            "failed": summary.failed,
            "skipped": summary.skipped,
            "errors": summary.errors,
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
