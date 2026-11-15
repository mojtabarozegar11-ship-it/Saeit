"""Print a safe, unsent Moj Prop offer draft for a reviewed lead.

This command is intentionally read-only. It never sends mail, changes the lead,
creates a payment intent, or advances a commercial status.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from core.models import MojPropRequest
from core.mojprop_offer_draft import build_offer_draft


class Command(BaseCommand):
    help = (
        "Print a non-binding Moj Prop offer draft for a consented lead in "
        "reviewing status; no email, payment, or state change is performed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--request-id",
            required=True,
            help="Exact MOJPROP request reference to review",
        )

    def handle(self, *args, **options):
        request_id = options["request_id"].strip()
        if not request_id.startswith("MOJPROP-"):
            raise CommandError("request-id must be a Moj Prop reference")
        lead = MojPropRequest.objects.filter(request_id=request_id).first()
        if lead is None:
            raise CommandError("Moj Prop request was not found")
        try:
            draft = build_offer_draft(lead)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(draft, ending="")
