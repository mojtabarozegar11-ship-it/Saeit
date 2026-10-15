#!/usr/bin/env python3
"""MojPlayWin-only 5-minute payment reconciliation entrypoint, fail-closed.

Uses bounded flock and never runs settlement until every release flag is true.
No wallet private key, signing or spending capability is present.
"""
import fcntl
import os
from pathlib import Path
import sys

ROOT=Path("/home/zomorod2/Saeit-staging")
LOCK=Path("/home/zomorod2/.mpw-book72-reconcile.lock")
REQUIRED=(
    "MPW_COMMERCE_RELEASE_READY",
    "MPW_COMMERCE_AUTORECONCILE_ENABLED",
    "MPW_COMMERCE_SETTLEMENT_ENABLED",
    "MPW_COMMERCE_REAL_RPC_ENABLED",
)


def run():
    if not ROOT.is_dir() or ROOT.is_symlink() or LOCK.is_symlink():
        raise RuntimeError("Authorized MojPlayWin app unavailable")
    fd=os.open(str(LOCK),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"r+") as handle:
        try:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print("MPW_RECONCILE_CONCURRENT_SKIP")
            return
        os.chdir(ROOT)
        sys.path.insert(0,str(ROOT))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
        import django
        django.setup()
        from django.conf import settings
        if settings.DEBUG is not False:
            raise RuntimeError("Refuse checkout in debug mode")
        if not all(getattr(settings,n,False) is True for n in REQUIRED):
            print("MPW_RECONCILE_SALES_OFF_NO_SCAN")
            return
        from django.core.management import call_command
        call_command("mpw_commerce_reconcile",verbosity=0)


if __name__=="__main__":
    run()
