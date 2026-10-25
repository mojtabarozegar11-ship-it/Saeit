"""Preview, or explicitly seed MojPlayWin-only internal manufacturing briefs."""
import json

from django.core.management.base import BaseCommand, CommandError

from core.mojplaywin_production_bank import prepare_main_site_cards, sync_main_site_production_bank


class Command(BaseCommand):
    help = "Preview 57 card signals and 24 internal manufacturing briefs. --apply is opt-in."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Create missing internal card signals and proposed briefs")
        parser.add_argument("--site", default="", help="Required explicit main-site confirmation with --apply")

    def handle(self, *args, **options):
        try:
            intake, signals = prepare_main_site_cards()
        except (KeyError, TypeError, ValueError) as exc:
            raise CommandError("Intake cards could not be safely mapped") from exc

        if not options["apply"]:
            self.stdout.write(json.dumps({
                "site": "mojplaywin.com",
                "mode": "dry_run_no_database_access",
                "signals_total": len(signals),
                "briefs_total": len(intake["production_proposals"]),
                "customer_orders_created": 0,
                "public_products_created": 0,
                "factory_tasks_created": 0,
            }, sort_keys=True))
            return

        if options["site"] != "mojplaywin.com":
            raise CommandError("Apply requires exactly --site mojplaywin.com")
        try:
            result = sync_main_site_production_bank()
        except Exception as exc:
            raise CommandError("Internal sync failed and transaction rolled back: " + type(exc).__name__) from exc
        self.stdout.write(json.dumps(result, sort_keys=True))
