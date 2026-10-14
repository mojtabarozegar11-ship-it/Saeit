"""One bounded scheduled automatic ETH/TRX settlement cycle.

Intentionally disabled by default. Do not configure periodic execution or
enable until merchant wallet ownership, RPC/network checks, production Django
integration, recovery/refund workflow and real low-value purchase are proven.
"""
from django.core.management.base import BaseCommand, CommandError
from mpw_native_checkout.autopay_worker import reconcile_once, AutoPayUnavailable


class Command(BaseCommand):
    help = "Run one opt-in verified ETH/TRX payment reconciliation cycle."

    def handle(self, *args, **options):
        try:
            result = reconcile_once()
        except AutoPayUnavailable as exc:
            raise CommandError("Native automatic payment cycle unavailable") from exc
        # No addresses, buyer data, tx IDs or wallet secrets in shared logs.
        self.stdout.write(
            f"NATIVE_AUTOPAY {result['state']} "
            f"scanned={result['scanned']} matched={result['matched']} "
            f"paid={result['paid']} rejected={result['rejected']}"
        )
        if result["state"] == "disabled":
            self.stdout.write("NO_PAID_STATE_CHANGES_FEATURE_FLAG_DISABLED")
