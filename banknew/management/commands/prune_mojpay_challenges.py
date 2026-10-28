"""Call daily before launch to bound ephemeral database growth."""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from banknew.models import LoginChallenge


class Command(BaseCommand):
    help = "Prune only expired MOJ Pay sign-in challenges; never touches accounts."

    def handle(self, *args, **options):
        old = timezone.now() - timedelta(hours=24)
        removed, _ = LoginChallenge.objects.filter(issued_at__lt=old).delete()
        self.stdout.write(f"Pruned {removed} expired login challenge rows.")
