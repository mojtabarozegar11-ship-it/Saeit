from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from company_messaging.models import Message
from company_messaging.services import dispatch_one


class Command(BaseCommand):
    help = "Dispatch due company messages (requires explicit --commit and enabled providers)."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--limit", type=int, default=20)

    def handle(self, *args, **opts):
        if opts["limit"] < 1 or opts["limit"] > 100:
            raise CommandError("--limit must be 1..100")
        if not opts["commit"]:
            self.stdout.write("PREVIEW ONLY: no external send")
            self.stdout.write(str(Message.objects.filter(status="queued",
                                                        scheduled_at__lte=timezone.now()).count()))
            return
        if not getattr(settings, "COMPANY_MESSAGING_SEND_ENABLED", False):
            raise CommandError("COMPANY_MESSAGING_SEND_ENABLED is false; no messages sent")
        ids = list(Message.objects.filter(status="queued", scheduled_at__lte=timezone.now())
                   .order_by("scheduled_at", "pk").values_list("pk", flat=True)[:opts["limit"]])
        results = {"accepted": 0, "uncertain": 0, "blocked": 0, "skipped": 0}
        for pk in ids:
            result = dispatch_one(pk)
            key = result if result in results else "skipped"
            results[key] += 1
        self.stdout.write("results="+str(results))
