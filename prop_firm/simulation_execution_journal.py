"""Internal persistence only; records remain UNATTESTED, never pass evidence.

Only a trusted server-side simulation session should call this API. It does
not authenticate price feeds or session ownership and must not be exposed as
a customer endpoint. Use an independently authenticated replay/evaluator
before any eligibility decision. No payout, account status or payment write.
"""
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
import hashlib
import json

from django.db import transaction
from django.db.models import Max
from django.utils import timezone as django_timezone

from config.mojprop_db_router import MOJPROP_DB_ALIAS
from .models import PropSimulationAccount, PropSimulationEvent
from .simulation_engine import ClosedExecutionRecord

SOURCE = "simulation_closure_unattested_v1"
SCHEMA = "mojprop.simulated.closure.v1"


class JournalConflict(ValueError):
    pass


def _decimal_text(value):
    if type(value) is not Decimal or not value.is_finite():
        raise JournalConflict("finite Decimal required")
    if len(value.as_tuple().digits) > 38 or abs(value.as_tuple().exponent) > 30:
        raise JournalConflict("decimal representation exceeds journal bounds")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if value.is_zero() else text


def _utc(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise JournalConflict("aware timestamp required")
    return value.astimezone(timezone.utc)


def _text(value, limit):
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise JournalConflict("invalid execution text field")
    return value


def _digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _payload(account, record):
    if type(record) is not ClosedExecutionRecord:
        raise JournalConflict("engine closure record required")
    fields = ("quantity","entry_price","exit_price","gross_pnl","commission","net_pnl")
    numbers = {key:_decimal_text(getattr(record,key)) for key in fields}
    exact = {key:Fraction(getattr(record,key)) for key in fields}
    if min(exact["quantity"],exact["entry_price"],exact["exit_price"]) <= 0 or exact["commission"] < 0:
        raise JournalConflict("invalid quantity, prices or fee")
    if record.side not in ("buy","sell"):
        raise JournalConflict("invalid side")
    expected = (exact["exit_price"]-exact["entry_price"])*exact["quantity"]*(1 if record.side=="buy" else -1)
    if expected != exact["gross_pnl"] or expected-exact["commission"] != exact["net_pnl"]:
        raise JournalConflict("closure accounting mismatch")
    opened, closed = _utc(record.opened_at), _utc(record.closed_at)
    if account.opened_at is None or not _utc(account.opened_at) <= opened <= closed <= django_timezone.now():
        raise JournalConflict("closure timestamp outside account history")
    if account.closed_at is not None and closed > _utc(account.closed_at):
        raise JournalConflict("closure after account close")
    if (type(record.opened_sequence) is not int or type(record.closed_sequence) is not int
            or not 0 <= record.opened_sequence < record.closed_sequence < 2**63):
        raise JournalConflict("invalid quote sequence")
    order_id=_text(record.order_id,160)
    payload={"schema":SCHEMA,"account_id":str(account.pk),"policy":account.policy_version,
             "order_id":order_id,"symbol":_text(record.symbol,64),"side":record.side,
             "opened_at":opened.isoformat(),"closed_at":closed.isoformat(),
             "opened_sequence":record.opened_sequence,"closed_sequence":record.closed_sequence,
             "reason":_text(record.reason,128),"provenance":"unattested",**numbers}
    ref="closure:v1:"+hashlib.sha256(order_id.encode()).hexdigest()
    return ref, payload, closed


def persist_closed_executions(*, account_ref, records):
    """Atomic append/retry for one account, sharing the account row lock.

    Existing records are returned only on exact payload/digest match.
    All event producers must serialize using the same account row lock.
    An event sequence is an account-journal index, NOT a quote sequence.
    """
    _text(account_ref,96)
    if not isinstance(records,(list,tuple)) or not 1 <= len(records) <= 500:
        raise JournalConflict("bounded nonempty batch required")
    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        account=PropSimulationAccount.objects.using(MOJPROP_DB_ALIAS).select_for_update().get(account_ref=account_ref)
        if not account.invoice_owner.settlement_verified or account.identity_id!=account.invoice_owner.identity_id:
            raise JournalConflict("account ownership or settlement invalid")
        events=PropSimulationEvent.objects.using(MOJPROP_DB_ALIAS).filter(account_id=account.pk)
        next_sequence=(events.aggregate(n=Max("sequence_no"))["n"] or 0)+1
        result=[]
        seen=set()
        for record in records:
            ref,payload,closed=_payload(account,record)
            if ref in seen:
                raise JournalConflict("duplicate closure in batch")
            seen.add(ref)
            digest=_digest(payload)
            old=events.filter(event_ref=ref).first()
            if old is not None:
                if (old.source!=SOURCE or old.event_type!=PropSimulationEvent.EventType.EXECUTION
                        or old.payload_digest!=digest or old.payload!=payload or old.occurred_at!=closed):
                    raise JournalConflict("conflicting closure replay")
                result.append(old.sequence_no)
                continue
            if account.status!=PropSimulationAccount.Status.ACTIVE:
                raise JournalConflict("new closure requires active simulation account")
            event=PropSimulationEvent.objects.using(MOJPROP_DB_ALIAS).create(
                account_id=account.pk,event_ref=ref,sequence_no=next_sequence,
                event_type=PropSimulationEvent.EventType.EXECUTION,source=SOURCE,
                occurred_at=closed,payload_digest=digest,payload=payload)
            result.append(event.sequence_no)
            next_sequence+=1
        return tuple(result)


def read_closed_execution_payloads(*, account_ref, after_sequence=0, limit=500):
    """Bounded restart inspection; integrity check is not authenticity proof."""
    _text(account_ref,96)
    if type(after_sequence) is not int or after_sequence<0 or type(limit) is not int or not 1<=limit<=500:
        raise JournalConflict("invalid journal pagination")
    events=PropSimulationEvent.objects.using(MOJPROP_DB_ALIAS).filter(
        account__account_ref=account_ref,source=SOURCE,sequence_no__gt=after_sequence,
        event_type=PropSimulationEvent.EventType.EXECUTION).order_by("sequence_no")[:limit]
    result=[]
    for event in events:
        p=event.payload
        if (not isinstance(p,dict) or p.get("schema")!=SCHEMA or p.get("provenance")!="unattested"
                or p.get("account_id")!=str(event.account_id) or _digest(p)!=event.payload_digest):
            raise JournalConflict("journal integrity mismatch")
        result.append((event.sequence_no,p))
    return tuple(result)
