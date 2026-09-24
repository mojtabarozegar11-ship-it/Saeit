import json

from django.core.management.base import BaseCommand, CommandError

from core.production_gate import ProductionGate


class Command(BaseCommand):
    help = "Run the read-only production readiness gate."

    def add_arguments(self, parser):
        parser.add_argument("--stale-after", type=int, default=900)
        parser.add_argument("--max-failed", type=int, default=0)
        parser.add_argument("--max-stale", type=int, default=0)

    def handle(self, *args, **options):
        try:
            result = ProductionGate().evaluate(
                stale_after_seconds=options["stale_after"],
                max_failed=options["max_failed"],
                max_stale=options["max_stale"],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        payload = {
            "ready": result.ready,
            "checks": result.checks,
            "reasons": list(result.reasons),
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        if not result.ready:
            raise CommandError("Production gate failed.")
