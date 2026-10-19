"""One-minute, fail-closed reconciliation for MojPlayWin's two approved book orders.

No keys, recipient addresses or buyer identifiers are logged. No payment
settlement runs unless every production payment control is explicitly enabled.
"""
import fcntl
import json
import os
import pathlib
import sys

ROOT = pathlib.Path("/home/zomorod2/Saeit-staging")
PRIVATE = pathlib.Path("/home/zomorod2/.mpw-commerce-two-books")
REQUIRED = (
    "MPW_COMMERCE_RELEASE_READY",
    "MPW_COMMERCE_AUTORECONCILE_ENABLED",
    "MPW_COMMERCE_SETTLEMENT_ENABLED",
    "MPW_COMMERCE_REAL_RPC_ENABLED",
)


def run():
    os.umask(0o077)
    if not ROOT.is_dir() or ROOT.is_symlink() or not PRIVATE.is_dir():
        raise RuntimeError("Trusted commerce deployment is missing")
    import django
    from django.conf import settings

    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    from mpw_commerce.auto_reconcile import reconcile_pending_orders

    with (PRIVATE / "reconcile.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"state": "previous_cycle_running"}
        if any(getattr(settings, key, False) is not True for key in REQUIRED):
            return {"state": "disabled"}
        report = reconcile_pending_orders()
        return {
            "state": report.get("state", "unknown"),
            "pending": int(report.get("pending", 0)),
            "matched": int(report.get("matched", 0)),
            "paid": int(report.get("paid", 0)),
            "rejected": int(report.get("rejected", 0)),
        }


if __name__ == "__main__":
    try:
        result = run()
        if "--self-check" in sys.argv or result.get("state") not in ("disabled", "idle"):
            print("MPW_WORKER_RESULT=" + json.dumps(result, sort_keys=True), flush=True)
    except Exception as exc:
        print("MPW_WORKER_ERROR=" + type(exc).__name__, flush=True)
        sys.exit(1)
