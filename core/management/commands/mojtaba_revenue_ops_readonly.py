"""Read-only operational evidence for the existing mojtaba.bot.ai agent.

Usage: python manage.py mojtaba_revenue_ops_readonly --days 30
Only aggregates; no email, webhook, transaction, network or database writes.
"""
import json

from django.core.management.base import BaseCommand, CommandError
from command_center.revenue_operations import build_operations_snapshot


class Command(BaseCommand):
    help = "Emit owner-private, aggregate CRM and commerce evidence (never collected cash)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, choices=(7, 30, 90), default=30)

    def handle(self, *args, **options):
        try:
            result = build_operations_snapshot(days=options["days"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
