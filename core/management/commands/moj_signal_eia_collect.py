"""Collect official weekly US crude oil inventory for editorial review."""
import hashlib
import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from services.mojtaba_eia_inventory_research import (
    fetch_eia_bytes, parse_inventory, SOURCE_URL, RIGHTS_URL,
)


class Command(BaseCommand):
    help = "Collect EIA government crude inventory observations without publishing or charging."

    def handle(self, *args, **options):
        try:
            data = fetch_eia_bytes()
            retrieved = timezone.now()
            latest, prior, current, previous = parse_inventory(data, today=retrieved.date())
        except (OSError, ValueError) as exc:
            raise CommandError("Official inventory data unavailable") from exc
        self.stdout.write(json.dumps({
            "source_url": SOURCE_URL, "rights_url": RIGHTS_URL,
            "retrieved_at": retrieved.isoformat(),
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "latest_date": latest.isoformat(), "comparison_date": prior.isoformat(),
            "stocks_thousand_barrels": current,
            "previous_stocks_thousand_barrels": previous,
            "change_thousand_barrels": current - previous,
            "publication": "not_published", "review_required": True,
        }, sort_keys=True))
