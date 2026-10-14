"""One DB-only activation pass after verified paid course orders.

Separate from blockchain watcher: does not call payment gateways or AI.
No production timer is installed; release feature gates default off.
"""
from django.core.management.base import BaseCommand, CommandError

from mpw_commerce.course_fulfillment import (
    fulfill_course_batch, CourseFulfillmentUnavailable,
)


class Command(BaseCommand):
    help="Activate existing approved courses purchased in paid MojPlayWin orders"

    def handle(self, *args, **options):
        try:
            result=fulfill_course_batch(limit=100)
        except CourseFulfillmentUnavailable as exc:
            raise CommandError("Paid course fulfillment is not ready") from exc
        self.stdout.write(
            "MPW_COURSE_AUTO_FULFILL state={state} processed={processed} enrolled={enrolled}".format(
                **result
            )
        )
