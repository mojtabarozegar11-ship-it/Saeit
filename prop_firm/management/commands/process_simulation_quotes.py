"""Controlled one-pass worker entry point; schedule only after operational approval."""
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from prop_firm.models import PropSimulationAccount
from prop_firm.simulation_runtime import trading_runtime_ready
from prop_firm.simulation_event_service import advance_account_quotes

class Command(BaseCommand):
    help = "Advance open simulated positions using the configured server-owned quote provider."

    def add_arguments(self, parser):
        parser.add_argument("--after-id", type=int, default=0)
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        if not trading_runtime_ready():
            raise CommandError("Simulation runtime is not ready.")
        limit, after = options["limit"], options["after_id"]
        if not 1 <= limit <= 500 or after < 0:
            raise CommandError("Invalid batch boundary.")
        # Expired accounts and accounts without any events do not need quotes.
        ids = list(PropSimulationAccount.objects.filter(
            status="active", pk__gt=after, event_head_sequence__gt=0,
            created_at__gt=timezone.now()-timedelta(days=60),
        ).order_by("pk").values_list("pk", flat=True)[:limit])
        failures = 0
        for account_id in ids:
            try:
                advance_account_quotes(account_id=account_id)
            except (ValidationError, ValueError, PropSimulationAccount.DoesNotExist):
                failures += 1
                self.stderr.write(f"Account {account_id}: quote processing blocked")
        self.stdout.write(f"processed={len(ids)-failures} blocked={failures} next_after_id={ids[-1] if ids else 0}")
        if failures:
            raise CommandError("One or more accounts need operator review.")
