"""Read-only collection of the official ECB research input for editorial review."""
import hashlib
import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from services.mojtaba_ecb_reference_research import (
    fetch_ecb_bytes, parse_rates, SOURCE_URL, RIGHTS_URL, NOTICE,
)


class Command(BaseCommand):
    help = "Collect ECB reference-rate observations for research review; does not publish or charge."

    def handle(self, *args, **options):
        try:
            data = fetch_ecb_bytes()
            retrieved = timezone.now()
            latest, prior, current, previous = parse_rates(data, today=retrieved.date())
        except (OSError, ValueError) as exc:
            raise CommandError("Official reference-rate collection unavailable") from exc
        self.stdout.write(json.dumps({
            "source_url": SOURCE_URL, "rights_url": RIGHTS_URL,
            "notice": NOTICE, "retrieved_at": retrieved.isoformat(),
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "latest_date": latest.isoformat(), "comparison_date": prior.isoformat(),
            "rates": {key: str(value) for key, value in current.items()},
            "comparison_rates": {key: str(value) for key, value in previous.items()},
            "publication": "not_published", "review_required": True,
        }, sort_keys=True))
