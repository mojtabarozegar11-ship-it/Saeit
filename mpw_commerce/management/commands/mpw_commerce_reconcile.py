"""One bounded reconciliation pass for a future trusted server-side scheduler.

No cron, daemon or public checkout routes are created here. Feature gates
default to OFF; never manually approve purchases after a valid chain receipt.
"""
from django.core.management.base import BaseCommand,CommandError

from mpw_commerce.auto_reconcile import (
    reconcile_pending_orders,ReconciliationUnavailable
)


class Command(BaseCommand):
    help="Run one read-only-discovery and independently verified sitewide settlement pass"

    def add_arguments(self,parser):
        parser.add_argument("--asset",choices=("ETH","TRX"),default=None)

    def handle(self,*args,**options):
        try:
            result=reconcile_pending_orders(asset_filter=options["asset"])
        except ReconciliationUnavailable as exc:
            raise CommandError("Commerce on-chain reconciliation not available") from exc
        # A temporary provider outage is never converted into an approved order.
        self.stdout.write(
            "MPW_COMMERCE_RECONCILE state={state} pending={pending} "
            "matched={matched} paid={paid} rejected={rejected}".format(**result)
        )
        return None
