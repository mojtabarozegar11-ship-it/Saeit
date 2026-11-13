from django.core.management.base import BaseCommand, CommandError
from core.weather_agent import run_daily_cycle


class Command(BaseCommand):
    help = (
        "Execute the canonical bot's weather capability; require verified "
        "legacy owner handoff before any forecast requests or publications."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--approval-grant-id", type=int, default=None,
            help="Explicit, one-time owner-approved grant for up to two model articles.",
        )

    def handle(self, *args, **options):
        try:
            result = run_daily_cycle(
                approval_grant_id=options.get("approval_grant_id")
            )
        except RuntimeError as exc:
            if str(exc) == "MOJTABA_CANONICAL_AGENT_NOT_PROVISIONED" or str(exc).startswith(
                "MOJTABA_LEGACY_HANDOFF_REQUIRED:"
            ):
                # Fail closed: no fake successful publication and no silently
                # running a former independent editorial identity.
                raise CommandError("WEATHER_MODULE_HANDOFF_BLOCKED: " + str(exc)) from exc
            raise
        self.stdout.write(self.style.SUCCESS(
            f"WEATHER_AGENT=OK DATE={result['date']} "
            f"PROVINCES={result['provinces']} "
            f"WEATHER_STORY={result['weather_story_id']} "
            f"WEATHER_NEW={int(result['weather_created'])} "
            f"RESEARCH_NEW={result['research_contents_created']} "
            "OWNER=mojtaba.bot.ai"
        ))
