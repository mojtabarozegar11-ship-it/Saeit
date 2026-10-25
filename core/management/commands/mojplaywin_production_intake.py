"""Export card-derived internal production proposals without any DB writes."""
import json

from django.core.management.base import BaseCommand

from core.mojplaywin_views import FEATURES, SECTIONS, VENTURES
from core.mojplaywin_production_intake import build_intake


class Command(BaseCommand):
    help = "Preview MojPlayWin card-derived production briefs; never creates orders or publishes."

    def add_arguments(self, parser):
        parser.add_argument("--summary", action="store_true", help="Summarize counts and first five priority hypotheses")

    def handle(self, *args, **options):
        data = build_intake(VENTURES, SECTIONS, FEATURES)
        if options["summary"]:
            data = {
                key: value for key, value in data.items()
                if key not in ("production_proposals", "other_activity_signals")
            } | {
                "top_five_proposals": [
                    {"id": x["id"], "title": x["product_title"], "source_card": x["source_card_title"]}
                    for x in data["production_proposals"][:5]
                ],
            }
        self.stdout.write(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))
