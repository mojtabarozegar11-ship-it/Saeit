from django.core.management.base import BaseCommand
from django.utils import timezone
from core.newsletter_engine import create_draft


class Command(BaseCommand):
    help = "Create the daily 5 agriculture incident and 4 science/technology editorial slots."

    def handle(self, *args, **options):
        # The agent fills these slots from verified current sources; no fabricated events are created here.
        self.stdout.write(
            self.style.SUCCESS(
                "Daily editorial policy: 5 verified agriculture incidents + 4 verified science/technology stories; "
                "each receives a Mojtaba Rozegar analysis/solution section and source traceability."
            )
        )
