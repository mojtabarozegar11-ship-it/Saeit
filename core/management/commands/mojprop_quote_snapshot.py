"""Read-only command for emitting one auditable Moj Prop quote snapshot."""
import json

from django.core.management.base import BaseCommand, CommandError

from core.models import MojPropOffer
from core.mojprop_quote_contract import QuoteContractError, make_quote_snapshot

class Command(BaseCommand):
    help = "Emit a buyer-safe Moj Prop quote snapshot; never charges or delivers."

    def add_arguments(self, parser):
        parser.add_argument("--offer-id", type=int, required=True)

    def handle(self, *args, **options):
        try:
            offer = MojPropOffer.objects.select_related("lead").get(pk=options["offer_id"])
        except MojPropOffer.DoesNotExist as exc:
            raise CommandError("offer not found") from exc
        try:
            snapshot = make_quote_snapshot(offer)
        except QuoteContractError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
