from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from company_marketing.models import Publication
from company_marketing.services import dispatch_publication


class Command(BaseCommand):
    help = "Publish approved company-owned posts. PREVIEW unless --commit and private kill-switch enabled."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **opts):
        if not 1 <= opts["limit"] <= 50:
            raise CommandError("limit out of 1..50")
        qs = Publication.objects.filter(status="approved", scheduled_at__lte=timezone.now())
        if not opts["commit"]:
            self.stdout.write("PREVIEW ONLY due="+str(qs.count()))
            return
        if not (getattr(settings, "COMPANY_MARKETING_PUBLISH_ENABLED", False)
                and getattr(settings, "COMPANY_MESSAGING_SEND_ENABLED", False)):
            raise CommandError("marketing publish kill-switch is OFF")
        ids = list(qs.order_by("scheduled_at", "pk").values_list("pk", flat=True)[:opts["limit"]])
        stats = {}
        for pk in ids:
            status = dispatch_publication(pk)
            stats[status] = stats.get(status, 0) + 1
        self.stdout.write("statuses="+str(stats))
