"""Fail-closed paid-order fulfillment dispatcher.

MojPlayWin's STORE (not this TRON scanner) authorizes the buyer and creates
an idempotent download entitlement. A 200 with a matching DELIVERY RECEIPT is
required before marking an invoice delivered. HTTP success alone is NEVER proof.
This module never handles wallets, seed phrases, private keys, or withdrawals.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener
from .core import CheckoutError

RECEIPT = re.compile(r'^[A-Za-z0-9_-]{8,128}$')
ALLOWED_HOSTS = frozenset(('mojplaywin.com', 'www.mojplaywin.com'))
MAX_REPLY_BYTES = 4096

class DeliveryUnavailable(CheckoutError):
    """Store is not ready. A signed event remains queued until acknowledged."""


def validate_endpoint(url: str) -> str:
    if not isinstance(url,str) or len(url)>300 or '\n' in url or '\r' in url:
        raise DeliveryUnavailable('Store endpoint is not configured')
    parts=urlsplit(url)
    if (parts.scheme!='https' or parts.hostname not in ALLOWED_HOSTS or
        parts.port not in (None,443) or parts.username or parts.password or
        parts.query or parts.fragment or
        not re.fullmatch(r'/api/payments/tron/fulfill/?',parts.path)):
        raise DeliveryUnavailable('Unapproved merchant fulfillment endpoint')
    return url


def payload_for(event: dict) -> dict:
    if (event.get('status') not in ('queued','leased') or
        not isinstance(event.get('merchant_order_id'),str) or
        not isinstance(event.get('event_id'),str) or
        not isinstance(event.get('txid'),str) or
        not re.fullmatch('[a-f0-9]{64}',event['txid']) or
        type(event.get('amount_sun')) is not int or event['amount_sun']<=0 or
        type(event.get('block_number')) is not int or event['block_number']<=0 or
        type(event.get('paid_ms')) is not int or event['paid_ms']<=0):
        raise DeliveryUnavailable('Payment evidence is incomplete')
    return {'event_id':event['event_id'], 'order_id':event['merchant_order_id'],
            'network':'tron-mainnet','currency':'TRX','amount_sun':event['amount_sun'],
            'txid':event['txid'],'block_number':event['block_number'],
            'paid_ms':event['paid_ms']}


def delivery_request(event: dict, *, endpoint: str, secret: str) -> Request:
    validate_endpoint(endpoint)
    if not isinstance(secret,str) or len(secret)<32 or len(secret)>512 or any(c in secret for c in '\n\r'):
        raise DeliveryUnavailable('Private store signing secret is missing or weak')
    raw=json.dumps(payload_for(event),ensure_ascii=True,separators=(',', ':'),sort_keys=True).encode('utf8')
    mac=hmac.new(secret.encode('utf8'),raw,hashlib.sha256).hexdigest()
    return Request(endpoint,data=raw,method='POST',headers={
        'Content-Type':'application/json','Accept':'application/json',
        'X-MPW-Event-ID':event['event_id'],'X-MPW-Event-Signature':'v1='+mac,
        'User-Agent':'MojPlayWin-TRON-Fulfillment/0.4'})


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def pinned_https_opener(request, *, timeout):
    # No 30x forwarding of a signed fulfillment event to an untrusted origin.
    return build_opener(NoRedirect()).open(request,timeout=timeout)


def send_to_store(event: dict, *, endpoint: str, secret: str, opener=pinned_https_opener) -> str:
    """Store must confirm the same order, event and a durable delivered receipt.

    Uses a strict no-redirect HTTPS client so signed events never follow redirects.
    Test openers are injection-only and must never be set from browser input.
    """
    request=delivery_request(event,endpoint=endpoint,secret=secret)
    try:
        with opener(request,timeout=12) as response:
            status=getattr(response,'status',None)
            if status!=200:
                raise DeliveryUnavailable('Merchant delivery not confirmed')
            if 'application/json' not in response.headers.get('Content-Type',''):
                raise DeliveryUnavailable('Merchant response content type invalid')
            data=response.read(MAX_REPLY_BYTES+1)
        if len(data)>MAX_REPLY_BYTES:
            raise DeliveryUnavailable('Merchant reply exceeded bound')
        result=json.loads(data.decode('utf8'))
    except (OSError, ValueError, UnicodeError, TimeoutError, HTTPError, URLError) as exc:
        raise DeliveryUnavailable('Merchant delivery endpoint unavailable') from exc
    if (type(result) is not dict or result.get('status')!='delivered' or
        result.get('event_id')!=event['event_id'] or
        result.get('order_id')!=event['merchant_order_id'] or
        not isinstance(result.get('delivery_id'),str) or
        not RECEIPT.fullmatch(result['delivery_id'])):
        raise DeliveryUnavailable('Merchant receipt is not independently verifiable')
    return result['delivery_id']


def drain_outbox(ledger, *, endpoint: str, secret: str, limit=20,
                 deliver=send_to_store, now_ms: int | None=None) -> dict:
    """At least once network delivery, exactly-once *entitlement* at store via event_id.

    An acknowledgement lost in flight is retried with SAME event ID.
    Site must implement transactional UNIQUE(event_id)/UNIQUE(order_id) before
    it gives a download. Store must reject purchases not bound to paid orders.
    """
    if type(limit) is not int or not 1<=limit<=100:
        raise DeliveryUnavailable('Invalid fulfillment limit')
    validate_endpoint(endpoint)
    if not isinstance(secret,str) or len(secret)<32:
        raise DeliveryUnavailable('Store delivery secret is not configured')
    counts={'attempted':0,'delivered':0,'retried':0}
    for _ in range(limit):
        claimed=ledger.claim_delivery(now_ms=now_ms)
        if claimed is None:
            break
        counts['attempted']+=1
        try:
            receipt=deliver(claimed,endpoint=endpoint,secret=secret)
            ledger.finish_delivery(claimed['invoice_id'],claimed['lease_token'],
                                   receipt_id=receipt,now_ms=now_ms)
            counts['delivered']+=1
        except (DeliveryUnavailable, CheckoutError, OSError, TimeoutError):
            ledger.finish_delivery(claimed['invoice_id'],claimed['lease_token'],
                                   error='merchant_delivery_unconfirmed',now_ms=now_ms)
            counts['retried']+=1
    return counts