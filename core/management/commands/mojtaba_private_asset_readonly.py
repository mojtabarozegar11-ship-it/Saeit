"""Owner-only local CLI: actual private file byte evidence, never delivery."""
import json

from django.core.management.base import BaseCommand, CommandError

from core.economic_master_agent import EconomicMasterAgent


class Command(BaseCommand):
    help = ("Read-only file digest+manifest evidence for ONE digital product. "
            "Requires separately approved private root configuration; "
            "does NOT enable buyer checkout, email, payment or delivery.")

    def add_arguments(self, parser):
        parser.add_argument("--product-id", type=int, required=True)

    def handle(self, *args, **options):
        product_id = options.get("product_id")
        if type(product_id) is not int or not 1 <= product_id <= 2147483647:
            raise CommandError("PRODUCT_IDENTIFIER_INVALID")
        report = EconomicMasterAgent().inspect_private_delivery_bytes_readonly(product_id)
        self.stdout.write(json.dumps(report, sort_keys=True, ensure_ascii=False))
