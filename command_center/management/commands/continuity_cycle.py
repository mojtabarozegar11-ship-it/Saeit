"""Run the safe continuity worker on cPanel cron or the company VPS."""
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from command_center.continuity import run_continuity_cycle


class Command(BaseCommand):
    help = "Review central-desk evidence and maintain internal continuity tickets; no external actions."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist internal tickets and audit records")
        parser.add_argument("--actor", help="Existing active staff username; mandatory with --apply")
        parser.add_argument("--horizon-hours", type=int, default=24)

    def handle(self, *args, **options):
        actor = None
        if options["apply"]:
            if not options.get("actor"):
                raise CommandError("--actor is required with --apply")
            actor = get_user_model().objects.filter(username=options["actor"], is_staff=True, is_active=True).first()
            if actor is None:
                raise CommandError("active staff actor not found")
        try:
            report = run_continuity_cycle(
                actor=actor, apply=options["apply"], horizon_hours=options["horizon_hours"]
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True))
