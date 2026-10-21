"""Read-only seller metrics and operator-only scanner health.

No keys, wallet addresses, PII, refund controls, or customer-side fund actions.
A heartbeat means that the scanner ran; it does not prove blockchain correctness.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import connection
from django.db.models import Sum
from django.utils import timezone

from .models import Merchant, MerchantAddress, DigitalProduct, Purchase, PurchaseScanState, PaymentDiscrepancy, ScannerRun


# Dedicated constant for a single MOJ-Commerce financial scanner per PostgreSQL DB.
# Use a session-level lock, not a transaction-level lock that expires too early.
SCAN_ADVISORY_LOCK_ID = 5631769340152039


class ConcurrentScanner(Exception):
    pass


@contextmanager
def exclusive_scanner():
    """Serialize scanner runs across cron processes on one PostgreSQL DB.

    Caller MUST keep the connection open for the whole scan, and this lock
    MUST be held before network reads or order writes. No SQLite fallback.
    """
    if connection.vendor != 'postgresql':
        raise RuntimeError('Scanner requires PostgreSQL row locks')
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [SCAN_ADVISORY_LOCK_ID])
        obtained = cursor.fetchone()[0]
    if obtained is not True:
        raise ConcurrentScanner('Another scanner is processing this database')
    try:
        yield
    finally:
        # Same Django DB session; use transaction-neutral unlock in finally.
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [SCAN_ADVISORY_LOCK_ID])
            if cursor.fetchone()[0] is not True:
                raise RuntimeError('Scanner lock unexpectedly lost')


def seller_snapshot(merchant: Merchant, *, limit=15, now=None) -> dict:
    """Only call with a merchant object already authorized by the request view."""
    if type(limit) is not int or not 1 <= limit <= 25:
        raise ValueError('Unsafe dashboard page size')
    now = timezone.now() if now is None else now
    orders = Purchase.objects.filter(merchant=merchant)
    paid = orders.filter(status=Purchase.Status.DELIVERED)
    pending = orders.filter(status=Purchase.Status.PENDING)
    # Snapshot: distinguish a time-expired but still undecided invoice.
    late = pending.filter(expires_at__lte=now)
    review = PaymentDiscrepancy.objects.filter(purchase__merchant=merchant)
    available = MerchantAddress.objects.filter(
        merchant=merchant, verified_at__isnull=False,
        verified_via=MerchantAddress.ProofMethod.SIGN_V2,
        purchase__isnull=True,
    ).count()
    totals=paid.aggregate(usd=Sum('usd_amount'))
    recent=(orders.select_related('product').order_by('-created_at','-pk')[:limit])
    items=[{'reference':o.reference,'product_title':o.product.title,
            'status':o.status,'usd_amount':str(o.usd_amount),
            'amount_sun':o.amount_sun,'expired':bool(o.status=='pending' and o.expires_at<=now),
            'created_at':o.created_at.isoformat()}
           for o in recent]
    flags=[]
    if merchant.status != Merchant.Status.APPROVED:
        flags.append('merchant_not_approved')
    if available == 0:
        flags.append('address_pool_exhausted')
    if review.exists():
        flags.append('payment_discrepancy_review_required')
    # Do not expose buyer identity, txids, wallet addresses, secrets, file keys.
    return {
        'merchant_id':str(merchant.public_id),'merchant_status':merchant.status,
        'totals':{'products':DigitalProduct.objects.filter(merchant=merchant,active=True).count(),
                  'orders':orders.count(),'paid_delivered':paid.count(),
                  'pending':pending.count(),'expired_pending':late.count(),
                  'confirmed_sales_usd':str(Decimal(totals['usd'] or 0).quantize(Decimal('0.01'))),
                  'payment_discrepancies':review.count(),
                  'available_verified_addresses':available},
        'warnings':flags,'recent_orders':items,
    }


def record_scanner_completion(run: ScannerRun, stats: dict | None = None, *, failed=False) -> None:
    """Persist whitelisted bounded counters; never write raw exceptions or RPC payloads."""
    if run.status != ScannerRun.Status.RUNNING:
        raise ValueError('Run is already completed')
    stats = stats or {}
    counts = {
        'scanned':stats.get('scanned',0),
        'fulfilled':stats.get('fulfilled',0),
        'failures':stats.get('failures',0),
        'discrepancies':stats.get('underpaid',0)+stats.get('overpaid',0),
        'manual_review':stats.get('manual_review',0),
    }
    for key,value in counts.items():
        if type(value) is not int or not 0 <= value <= 10_000:
            raise ValueError('Invalid scanner metric')
        setattr(run,key,value)
    run.status=ScannerRun.Status.FAILED if failed else ScannerRun.Status.OK
    run.error_code='SCAN_FAILED' if failed else ''
    run.finished_at=timezone.now()
    run.save(update_fields=['status','error_code','finished_at',*counts.keys()])


def scanner_health(*, now=None, stale_seconds=300, overdue_seconds=180) -> dict:
    """Operator-grade read-only diagnostic. Caller must be superuser in the view.

    No production-ready or 'healthy' claim without ALL runtime prerequisites.
    No API keys, wallet addresses, IPs, txids or buyer identities in response.
    """
    if not 60 <= stale_seconds <= 86400 or not 60 <= overdue_seconds <= 86400:
        raise ValueError('Health thresholds outside policy')
    now=timezone.now() if now is None else now
    now_ms=int(now.timestamp()*1000)
    run=ScannerRun.objects.order_by('-started_at','-pk').first()
    due=(PurchaseScanState.objects.filter(purchase__status=Purchase.Status.PENDING,
                                         next_scan_ms__lte=now_ms-overdue_seconds*1000)
         .count())
    missing_states=Purchase.objects.filter(status=Purchase.Status.PENDING, scan_state__isnull=True).count()
    failures=(PurchaseScanState.objects.filter(purchase__status=Purchase.Status.PENDING,
                                              failures__gte=3).count())
    awaiting_review=PaymentDiscrepancy.objects.count()
    ready=(connection.vendor=='postgresql' and
           bool(getattr(settings,'MOJ_COMMERCE_SCANNER_ENABLED',False)) and
           bool(getattr(settings,'MOJ_COMMERCE_CHECKOUT_ENABLED',False)) and
           callable(getattr(settings,'MOJ_COMMERCE_FINALIZED_TRON_CHECKER',None)) and
           isinstance(getattr(settings,'MOJ_COMMERCE_FULFILL_SECRET',None),str) and
           len(getattr(settings,'MOJ_COMMERCE_FULFILL_SECRET',''))>=32)
    if not getattr(settings,'MOJ_COMMERCE_SCANNER_ENABLED',False):
        status='disabled'
    elif not ready:
        status='not_configured'
    elif run is None:
        status='never_run'
    elif (now-run.started_at).total_seconds()>stale_seconds:
        status='stale'
    elif run.status==ScannerRun.Status.RUNNING:
        status='running'
    elif run.status==ScannerRun.Status.FAILED or run.failures or failures or due or missing_states:
        status='degraded'
    else:
        status='healthy'
    # A passing heartbeat only confirms checks were attempted, not real funds.
    return {'status':status,'scanner_enabled':bool(getattr(settings,'MOJ_COMMERCE_SCANNER_ENABLED',False)),
            'database_postgresql':connection.vendor=='postgresql',
            'last_run_started_at':run.started_at.isoformat() if run else None,
            'last_run_finished_at':run.finished_at.isoformat() if run and run.finished_at else None,
            'last_run_status':run.status if run else None,
            'last_run_scanned':run.scanned if run else 0,
            'last_run_fulfilled':run.fulfilled if run else 0,
            'last_run_failures':run.failures if run else 0,
            'overdue_scans':due,'missing_scan_states':missing_states,
            'orders_with_repeated_scan_failures':failures,
            'payment_discrepancies':awaiting_review,
            'warnings':[code for condition,code in (
                (status not in ('healthy','running'),'scanner_attention_required'),
                (due>0,'backlog_overdue'),(missing_states>0,'missing_scan_state'),
                (failures>0,'repeated_scan_failures'),
                (awaiting_review>0,'payment_discrepancy_review_required'),
            ) if condition]}