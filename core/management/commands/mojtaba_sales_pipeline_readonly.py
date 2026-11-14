"""CLI sales pipeline snapshot: no customer contact, checkout or database writes."""
import json
from django.core.management.base import BaseCommand
from core.company_sales_pipeline import sales_pipeline_snapshot


class Command(BaseCommand):
    help = "Owner-controlled read-only inquiry queue summary for mojtaba.bot.ai."

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(
            sales_pipeline_snapshot(), ensure_ascii=False, sort_keys=True,
        ))
