"""One-minute, fail-closed reconciliation for MojPlayWin's two approved book orders.

No keys, recipient addresses or buyer identifiers are logged. No payment
settlement runs unless every production payment control is explicitly enabled.
"""
import fcntl
import json
import os
import pathlib
import sys
import tempfile
import time

ROOT = pathlib.Path("/home/zomorod2/Saeit-staging")
PRIVATE = pathlib.Path("/home/zomorod2/.mpw-commerce-two-books")
REQUIRED = (
    "MPW_COMMERCE_RELEASE_READY",
    "MPW_COMMERCE_AUTORECONCILE_ENABLED",
    "MPW_COMMERCE_SETTLEMENT_ENABLED",
    "MPW_COMMERCE_REAL_RPC_ENABLED",
)

def heartbeat(report, *, error=None):
    """Publish only nonsensitive counters and one trustworthy UTC heartbeat."""
    if not PRIVATE.is_dir() or PRIVATE.is_symlink():
        return
    now = int(time.time())
    state = report.get("state", "error") if isinstance(report, dict) else "error"
    record = {
        "schema": 1,
        "utc_epoch": now,
        "state": state,
        "healthy": error is None and state in ("idle", "scanned", "disabled"),
        "pending": int(report.get("pending", 0)) if isinstance(report, dict) else 0,
        "matched": int(report.get("matched", 0)) if isinstance(report, dict) else 0,
        "paid": int(report.get("paid", 0)) if isinstance(report, dict) else 0,
        "rejected": int(report.get("rejected", 0)) if isinstance(report, dict) else 0,
        "error_type": error or "",
    }
    fd, temporary = tempfile.mkstemp(prefix=".reconcile-monitor-", dir=str(PRIVATE))
    try:
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            json.dump(record, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, PRIVATE / "worker-heartbeat.json")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


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
        from mpw_commerce.models import CommerceInvoice
        pending = CommerceInvoice.objects.filter(
            status=CommerceInvoice.Status.AWAITING,
            order__status="pending",
        ).select_related("order")[:101]
        invoices = list(pending)
        if len(invoices) > 100:
            return {"state": "unbounded_scope_denied"}
        for invoice in invoices:
            product_ids = set(invoice.order.items.values_list("product_id", flat=True))
            if len(product_ids) != 1 or not product_ids.issubset({72, 225}):
                return {"state": "other_product_scope_denied"}
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
        if "--self-check" not in sys.argv:
            heartbeat(result)
        if result.get("state") in ("unbounded_scope_denied", "other_product_scope_denied"):
            raise RuntimeError("Reconciliation scope was denied")
        if "--self-check" in sys.argv or result.get("state") not in ("disabled", "idle"):
            print("MPW_WORKER_RESULT=" + json.dumps(result, sort_keys=True), flush=True)
    except Exception as exc:
        if "--self-check" not in sys.argv:
            heartbeat({"state": "error"}, error=type(exc).__name__)
        print("MPW_WORKER_ERROR=" + type(exc).__name__, flush=True)
        sys.exit(1)
