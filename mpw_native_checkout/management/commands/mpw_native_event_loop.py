"""Opt-in single-host event-driven ETH/TRX settlement worker, RELEASE BLOCKED.

This is a *future* integration entrypoint; it is not scheduled or installed
on the live Django app. Live activation requires wallet ownership attestations,
audited sender-signature verification, successful mainnet receipt test and
approved DB migration. Without explicit server-side release gate it refuses
to start; without an open invoice it never calls chain APIs or OpenAI.

The local socket accepts only authenticated checkout wake/close events. It
does not trust those events as payment proof. Every candidate must pass the
separate independent mainnet RPC verifier + DB ledger transaction.
"""
from pathlib import Path
import os
import stat

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from mpw_native_checkout.autopay_worker import reconcile_once
from scripts.mojplaywin_cpanel_local_event_worker import run_local_worker


def _load_secret():
    filename = getattr(settings, "MPW_NATIVE_EVENT_SECRET_FILE", None)
    if not isinstance(filename, str) or not Path(filename).is_absolute():
        raise CommandError("Approved private event key file required")
    key_file=Path(filename)
    try:
        st=key_file.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid()
                or st.st_mode & 0o077 or not 32<=st.st_size<=1024):
            raise CommandError("Private event key permissions not approved")
        secret=key_file.read_bytes().strip()
    except OSError as exc:
        raise CommandError("Private event key unavailable") from exc
    if len(secret)<32:
        raise CommandError("Event signing key too short")
    return secret


class Command(BaseCommand):
    help="Future opt-in event-driven ETH/TRX settlement. Live feature is disabled."

    def handle(self, *args, **options):
        if getattr(settings,"MPW_NATIVE_EVENT_ENABLED",False) is not True:
            raise CommandError("Native event ingress not approved")
        if getattr(settings,"MPW_NATIVE_AUTOPAY_ENABLED",False) is not True:
            raise CommandError("Native auto-settlement not approved")
        if getattr(settings,"MPW_NATIVE_RELEASE_APPROVED",False) is not True:
            raise CommandError("Production safety gates not approved")
        approval=getattr(settings,"MPW_NATIVE_MERCHANT_PROOFS",{})
        if (not isinstance(approval,dict) or
                approval.get("ETH") is not True or approval.get("TRX") is not True):
            raise CommandError("Receiver wallet ownership not attested")
        root=getattr(settings,"MPW_NATIVE_EVENT_HOME",None)
        if not isinstance(root,str) or not Path(root).is_absolute():
            raise CommandError("Approved private local event directory missing")
        secret=_load_secret()

        def scan_eth():
            # Exactly one coin and its invoice lookback; never poll without an
            # event. Count only, do not propagate customer or transaction data.
            result=reconcile_once(asset_filter="ETH")
            return [None] * result.get("matched",0)

        def scan_trx():
            result=reconcile_once(asset_filter="TRX")
            return [None] * result.get("matched",0)

        self.stdout.write("MPW_EVENT_RECONCILIATION_READY_SAME_HOST")
        run_local_worker(root,secret,eth_scan=scan_eth,trx_scan=scan_trx)
