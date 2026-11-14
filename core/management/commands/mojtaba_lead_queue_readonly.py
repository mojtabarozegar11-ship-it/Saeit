"""Read-only CRM queue for a trusted owner/operator shell, not an external API.

python manage.py mojtaba_lead_queue_readonly --status new --kind research
Never transmits, invoices, contacts, or exports personal customer fields.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from command_center.lead_workqueue import lead_workqueue_snapshot


class Command(BaseCommand):
    help = "Output a PII-free, read-only, paginated CRM lead queue."

    def add_arguments(self, parser):
        parser.add_argument(
            "--status", default="all",
            choices=("all", "new", "reviewing", "approved"),
        )
        parser.add_argument(
            "--kind", default="all",
            choices=("all", "research", "technology", "project", "commercial", "media"),
        )
        parser.add_argument("--page", type=int, default=1)

    def handle(self, *args, **options):
        try:
            data = lead_workqueue_snapshot(
                status=options["status"], kind=options["kind"],
                page=options["page"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(data, ensure_ascii=False, sort_keys=True))
