"""Owner-invoked calculation via the existing mojtaba.bot.ai command environment.

Example (illustrative only):
python manage.py mojtaba_quote_scenario_readonly --scenario-json '{"currency":"USD",...}'
Do NOT pass customer information, account keys or an order to this calculator.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from core.revenue_unit_economics import compute_quote_scenario


class Command(BaseCommand):
    help = "Validate a quote scenario; output economics without creating a price, invoice or payment."

    def add_arguments(self, parser):
        parser.add_argument("--scenario-json", required=True, type=str)

    def handle(self, *args, **options):
        raw = options["scenario_json"]
        if len(raw) > 4096:
            raise CommandError("scenario-json exceeds 4096 chars")
        try:
            payload = json.loads(raw)
            result = compute_quote_scenario(payload)
        except (ValueError, TypeError) as exc:
            raise CommandError(f"invalid quote scenario: {exc}") from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
