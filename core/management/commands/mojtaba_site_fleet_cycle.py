"""Single-entrypoint site observability for Mojtaba.bot.ai.

Private factory, payments, trading, publishing, cron and site mutations are
explicitly OUT OF SCOPE. May run against real public websites with bounded GET.
The caller is a *single* canonical bot; this command never creates an Agent.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from core.mojtaba_site_fleet import CANONICAL_BOT, inventory, run_one_bot_public_cycle
from core.models import Agent


class Command(BaseCommand):
    help = "Inspect two site-owned public surfaces under one bot identity (read-only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--observe-public", action="store_true",
            help="Perform bounded GET of 14 allowlisted public routes; no site writes.",
        )

    def handle(self, *args, **options):
        if options.get("observe_public"):
            # A string constant in a JSON report is not proof of a real bot.
            # Public observations must be owned by the actual, active canonical
            # Django Agent record. Never auto-create an identity as a side effect.
            if Agent.objects.filter(code="mojtaba-bot-ai", active=True).count() != 1:
                raise CommandError("CANONICAL_BOT_RUNTIME_IDENTITY_NOT_PROVISIONED")
            report = run_one_bot_public_cycle()
        else:
            report = inventory()
        if report.get("canonical_bot") != CANONICAL_BOT:
            raise CommandError("CANONICAL_BOT_IDENTITY_MISMATCH")
        self.stdout.write(json.dumps(
            report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ))
