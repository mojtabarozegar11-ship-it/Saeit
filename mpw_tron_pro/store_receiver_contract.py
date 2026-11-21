"""Reusable STRICT validation for the site's future Django fulfillment endpoint.

This is a contract, not an installed MojPlayWin route. The real store MUST do
an atomic order lookup + entitlement grant under UNIQUE(event_id, order_id).
Never call delivery "complete" on HMAC alone; confirm paid order + product.
"""
from __future__ import annotations
import hmac
import hashlib
import json
import re
from .core import CheckoutError
from .store_delivery import DeliveryUnavailable

SIGNATURE = re.compile(r'^v1=[a-f0-9]{64}$')
ORDER = re.compile(r'^[A-Za-z0-9_-]{10,80}$')
EVENT = re.compile(r'^mpwtr_[a-f0-9]{64}$')


def verify_store_event(raw: bytes, signature: str, secret: str) -> dict:
    if (not isinstance(raw,bytes) or not 0<len(raw)<=4096 or
        not isinstance(signature,str) or not SIGNATURE.fullmatch(signature) or
        not isinstance(secret,str) or len(secret)<32):
        raise DeliveryUnavailable('Invalid signed delivery')
    expected='v1='+hmac.new(secret.encode('utf8'),raw,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,signature):
        raise DeliveryUnavailable('Delivery signature mismatch')
    def strict(pairs):
        seen={}
        for key,value in pairs:
            if key in seen:raise DeliveryUnavailable('Duplicate field in delivery')
            seen[key]=value
        return seen
    try:
        obj=json.loads(raw.decode('utf8'),object_pairs_hook=strict,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (ValueError,UnicodeError) as exc:
        raise DeliveryUnavailable('Invalid delivery JSON') from exc
    if (not isinstance(obj,dict) or
        set(obj) != {'event_id','order_id','network','currency','amount_sun','txid','block_number','paid_ms'} or
        not isinstance(obj.get('event_id'),str) or not EVENT.fullmatch(obj['event_id']) or
        not isinstance(obj.get('order_id'),str) or not ORDER.fullmatch(obj['order_id']) or
        obj['network']!='tron-mainnet' or obj['currency']!='TRX' or
        not isinstance(obj.get('txid'),str) or not re.fullmatch(r'[a-f0-9]{64}',obj['txid']) or
        any(type(obj.get(k)) is not int or obj[k]<=0 for k in ('amount_sun','block_number','paid_ms'))):
        raise DeliveryUnavailable('Untrusted delivery payload')
    return obj