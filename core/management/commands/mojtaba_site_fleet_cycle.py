"""Single-entrypoint site observability for Mojtaba.bot.ai.

Private factory, payments, trading, publishing, cron and site mutations are
explicitly OUT OF SCOPE. May run against real public websites with bounded GET.
The caller is a *single* canonical bot; this command never creates an Agent.
"""
import json
import uuid

from django.core.management.base import BaseCommand, CommandError

from core.mojtaba_site_fleet import CANONICAL_BOT, inventory, run_one_bot_public_cycle
from core.mojtaba_site_receipts import record_public_cycle
from core.mojtaba_site_private_collector import collect_private_mpw_as_canonical_bot
from core.models import Agent


class Command(BaseCommand):
    help = "Inspect two site-owned public surfaces under one bot identity (read-only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--record-receipt", action="store_true",
            help="Persist redacted one-cycle public monitor evidence in AuditLog.",
        )
        parser.add_argument(
            "--collect-private-mpw", action="store_true",
            help="Explicit cPanel-only private MPW history refresh; old Cron must be absent.",
        )
        parser.add_argument(
            "--observe-public", action="store_true",
            help="Perform bounded GET of 14 allowlisted public routes; no site writes.",
        )

    def handle(self, *args, **options):
        if options.get("record_receipt") and not options.get("observe_public"):
            raise CommandError("RECORD_REQUIRES_EXPLICIT_PUBLIC_OBSERVATION")
        if options.get("collect_private_mpw") and not (
            options.get("observe_public") and options.get("record_receipt")
        ):
            raise CommandError("PRIVATE_COLLECTION_REQUIRES_CANONICAL_RECORDED_CYCLE")
        if options.get("observe_public"):
            # A string constant in a JSON report is not proof of a real bot.
            # Public observations must be owned by the actual, active canonical
            # Django Agent record. Never auto-create an identity as a side effect.
            if Agent.objects.filter(code="mojtaba-bot-ai", active=True).count() != 1:
                raise CommandError("CANONICAL_BOT_RUNTIME_IDENTITY_NOT_PROVISIONED")
            report = run_one_bot_public_cycle()
            if options.get("record_receipt"):
                report["durable_receipt"] = record_public_cycle(
                    report, cycle_id=uuid.uuid4().hex
                )
            if options.get("collect_private_mpw"):
                report["private_mpw_history"] = collect_private_mpw_as_canonical_bot()
        else:
            report = inventory()
        if report.get("canonical_bot") != CANONICAL_BOT:
            raise CommandError("CANONICAL_BOT_IDENTITY_MISMATCH")
        self.stdout.write(json.dumps(
            report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ))
