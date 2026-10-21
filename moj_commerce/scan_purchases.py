"""Bounded automatic scanning of Django-native seller-isolated TRX invoices.

One PostgreSQL purchase is the source of truth. No separate global SQLite
wallet pool or cross-database checkout commit. Discovery is untrusted; only a
solidified native TRX body AND receipt make an eligible delivery event.
Do not schedule this source on any live VPS until merchant onboarding, backup,
monitoring, provider reliability and owner approval are separately verified.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import time
from django.conf import settings
from django.db import transaction, IntegrityError, DatabaseError
from django.utils import timezone
from mpw_tron_pro.core import CheckoutError, ExpectedTransfer, inspect_finalized_trx
from mpw_tron_pro.reconcile import incoming_candidates
from mpw_tron_pro.rpc import finalized_records
from .models import Purchase, PurchaseScanState, PaymentDiscrepancy
from .services import CommerceRejected, CommerceUnavailable, finalize_signed_purchase


class ScanUnavailable(Exception):
    pass


def _event(purchase, proof):
    event_id = 'mpwtr_' + hashlib.sha256(
        ('moj:commerce:trx:v1:' + purchase.reference + ':' + proof.txid).encode('ascii')).hexdigest()
    return {'event_id':event_id,'order_id':purchase.reference,
            'network':'tron-mainnet','currency':'TRX','amount_sun':proof.amount_sun,
            'txid':proof.txid,'block_number':proof.block_number,'paid_ms':proof.block_ms}


def _mark_scan(state_id, *, now_ms, failure=False):
    with transaction.atomic():
        state=PurchaseScanState.objects.select_for_update().get(pk=state_id)
        state.failures=min(10,state.failures+1) if failure else 0
        delay=min(300_000, 20_000 * (2**min(state.failures,4)))
        state.next_scan_ms=now_ms+delay
        state.last_scan_ms=now_ms
        state.save(update_fields=['failures','next_scan_ms','last_scan_ms'])


def scan_purchases_once(*, max_orders=10, discover=incoming_candidates,
                        fetch=finalized_records, verifier=None, secret=None,
                        api_key='', now_ms=None):
    """Reconcile at most N due invoices and fail closed on mismatched payments.

    Real cron may call via an owner-approved service, but nothing in this
    repository schedules it or gives it access to a wallet private key.
    """
    if not getattr(settings,'MOJ_COMMERCE_SCANNER_ENABLED',False):
        raise ScanUnavailable('Scanner is disabled')
    if type(max_orders) is not int or not 1 <= max_orders <= 25:
        raise ValueError('Invalid scanner batch size')
    if not callable(verifier):
        verifier=getattr(settings,'MOJ_COMMERCE_FINALIZED_TRON_CHECKER',None)
    if not callable(verifier):
        raise ScanUnavailable('An independent finalized-chain checker is required')
    if secret is None:
        secret=getattr(settings,'MOJ_COMMERCE_FULFILL_SECRET','')
    if not isinstance(secret,str) or not 32 <= len(secret) <= 512:
        raise ScanUnavailable('A private delivery secret is required')
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    if type(now_ms) is not int or now_ms <= 0:
        raise ValueError('Invalid scan time')
    states=(PurchaseScanState.objects.filter(
        purchase__status=Purchase.Status.PENDING, next_scan_ms__lte=now_ms)
        .select_related('purchase__destination','purchase__merchant','purchase__product')
        .order_by('next_scan_ms','pk')[:max_orders])
    stats={'scanned':0,'fulfilled':0,'underpaid':0,'overpaid':0,
           'failures':0,'manual_review':0}
    for state in states:
        stats['scanned']+=1
        order=state.purchase
        issued_ms=int(order.created_at.timestamp()*1000)
        expires_ms=int(order.expires_at.timestamp()*1000)
        failed=False
        try:
            # An invalid/legacy manual address may NEVER be scanned as a seller payout.
            if (order.destination.merchant_id != order.merchant_id or
                order.destination.verified_at is None or
                order.destination.verified_via != 'tron-sign-v2' or
                order.merchant.status != 'approved' or
                order.network != 'tron-mainnet'):
                raise CommerceRejected('Order wallet/merchant proof is invalid')
            discovered=discover(order.destination.address,issued_ms,expires_ms,api_key=api_key)
            if not isinstance(discovered,list) or len(discovered)>600:
                raise CheckoutError('Unbounded transaction index response')
            for txid in discovered:
                if not isinstance(txid,str):
                    raise CheckoutError('Malformed transaction identifier')
                # Independent read of solidified receipt/body is mandatory.
                body, receipt=fetch(txid,api_key=api_key)
                expected=ExpectedTransfer(txid,order.destination.address,
                                          order.amount_sun,issued_ms,expires_ms)
                proof=inspect_finalized_trx(body,receipt,expected)
                if proof.amount_sun != order.amount_sun:
                    kind='underpaid' if proof.amount_sun < order.amount_sun else 'overpaid'
                    try:
                        PaymentDiscrepancy.objects.get_or_create(
                            txid=txid,defaults={'purchase':order,
                                               'amount_sun':proof.amount_sun,'kind':kind})
                    except IntegrityError:
                        pass
                    stats[kind]+=1
                    continue
                event=_event(order,proof)
                raw=json.dumps(event,separators=(',',':'),sort_keys=True).encode('utf8')
                sig='v1='+hmac.new(secret.encode('utf8'),raw,hashlib.sha256).hexdigest()
                try:
                    # Second *independent* source read in trusted merchant receiver.
                    # Same-database receipt is idempotent across retries/crashes.
                    receipt_data=finalize_signed_purchase(raw,sig,secret,verifier)
                    if receipt_data.get('status')=='delivered':
                        stats['fulfilled']+=1
                        break
                except CommerceUnavailable:
                    failed=True
                    break
                except (CommerceRejected,IntegrityError):
                    stats['manual_review']+=1
        except (CheckoutError,CommerceRejected):
            stats['manual_review']+=1
            failed=True
        except (CommerceUnavailable,DatabaseError,OSError,TimeoutError,ConnectionError,ValueError):
            failed=True
        finally:
            _mark_scan(state.pk,now_ms=now_ms,failure=failed)
            if failed:
                stats['failures']+=1
    return stats