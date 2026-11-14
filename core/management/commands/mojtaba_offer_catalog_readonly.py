"""Source-only six-service catalogue view: NO prices or active contract offers.

python manage.py mojtaba_offer_catalog_readonly
python manage.py mojtaba_offer_catalog_readonly --service-code AGR-01
"""
import json

from django.core.management.base import BaseCommand

from core.service_sales_controls import SERVICE_CARDS, list_service_cards, service_card


class Command(BaseCommand):
    help = "Read draft six-service descriptions and delivery limits; no price or sale."

    def add_arguments(self, parser):
        parser.add_argument(
            "--service-code", default=None, choices=tuple(SERVICE_CARDS),
        )

    def handle(self, *args, **options):
        cards = (
            [service_card(options["service_code"])]
            if options["service_code"] else list_service_cards()
        )
        self.stdout.write(json.dumps({
            "agent": "mojtaba.bot.ai",
            "source_status": "DRAFT_NONBINDING_NO_EXTERNAL_SALE",
            "services": cards,
            "verified_cash": None,
        }, ensure_ascii=False, sort_keys=True))
