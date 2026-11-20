"""Account-scoped, fail-closed persistence of UNATTESTED simulation checkpoints.

No public endpoint, market-data credential, customer entitlement or reward
settlement. The isolated DB provides a restart audit trail, but authenticated
execution provenance and the transaction-coupled live runner are separate
release prerequisites. Recovered engines are always blocked.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import hashlib
import json

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from config.mojprop_db_router import MOJPROP_DB_ALIAS
from .models import PropSimulationAccount, PropSimulationEvent
from .simulation_engine import SimulationEngine, ClosedExecutionRecord
from .simulation_execution_journal import (
    JournalConflict, SOURCE as CLOSURE_SOURCE, _payload as closure_payload,
    _digest,
)
from .simulation_journal_accounting import flush_engine_closures
from .simulation_checkpoint import export_checkpoint, recover_quarantined_engine

SOURCE="sim_engine_checkpoint_unattested_v1"
SCHEMA="mojprop.simulated.checkpoint.event.v1"
LIMIT=10000
MAX_JSON_BYTES=1024*1024


@dataclass(frozen=True)
class QuarantinedCheckpoint:
    engine: SimulationEngine
    event_sequence: int
    closure_count: int
    journal_digest: str
    resumable: bool = False


def _account_ref(value):
    if type(value) is not str or not value.strip() or len(value)>96:
        raise JournalConflict("invalid account ref")
    return value


def _canonical(p):
    b=json.dumps(p,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
    if len(b)>MAX_JSON_BYTES:
        raise JournalConflict("checkpoint payload too large")
    return b


def _load_closures(account):
    rows=(PropSimulationEvent.objects.using(MOJPROP_DB_ALIAS)
          .filter(account=account,event_type=PropSimulationEvent.EventType.EXECUTION,source=CLOSURE_SOURCE)
          .order_by("sequence_no")[:LIMIT+1])
    records=[]
    signature=[]
    previous=-1
    ids=set()
    for row in rows:
        if len(records)>=LIMIT:
            raise JournalConflict("too many persisted closures")
        p=row.payload
        if not isinstance(p,dict) or _digest(p)!=row.payload_digest:
            raise JournalConflict("persisted closure digest mismatch")
        try:
            record=ClosedExecutionRecord(
                order_id=p["order_id"],symbol=p["symbol"],side=p["side"],
                quantity=Decimal(p["quantity"]),entry_price=Decimal(p["entry_price"]),
                exit_price=Decimal(p["exit_price"]),
                opened_sequence=p["opened_sequence"],closed_sequence=p["closed_sequence"],
                opened_at=datetime.fromisoformat(p["opened_at"]),
                closed_at=datetime.fromisoformat(p["closed_at"]),
                gross_pnl=Decimal(p["gross_pnl"]),commission=Decimal(p["commission"]),
                net_pnl=Decimal(p["net_pnl"]),reason=p["reason"],
            )
        except (KeyError,TypeError,ValueError,ArithmeticError) as exc:
            raise JournalConflict("unreadable closure payload") from exc
        expected_ref,expected_payload,expected_when=closure_payload(account,record)
        if (expected_payload!=p or expected_ref!=row.event_ref or
                expected_when!=row.occurred_at or record.order_id in ids or row.sequence_no<=previous):
            raise JournalConflict("persisted closure contradicts account journal")
        previous=row.sequence_no
        ids.add(record.order_id)
        records.append(record)
        signature.append((row.sequence_no,row.event_ref,row.payload_digest))
    signature_digest=hashlib.sha256(_canonical(signature)).hexdigest()
    return tuple(records),signature_digest,previous if records else 0


def _account_locked(account_ref):
    account=PropSimulationAccount.objects.using(MOJPROP_DB_ALIAS).select_for_update().get(
        account_ref=_account_ref(account_ref))
    if (not account.invoice_owner.settlement_verified or
            account.identity_id!=account.invoice_owner.identity_id):
        raise JournalConflict("simulation ownership/settlement mismatch")
    return account


def _validate_account_engine(account,engine):
    if type(engine) is not SimulationEngine:
        raise JournalConflict("internal engine required")
    if account.status != PropSimulationAccount.Status.ACTIVE:
        raise JournalConflict("only active simulation may create new checkpoints")
    if engine.starting_balance!=account.starting_capital_usd:
        raise JournalConflict("engine starting capital differs from account")
    if engine.last_quote_time is not None and (
            account.opened_at is None or engine.last_quote_time<account.opened_at):
        raise JournalConflict("quote precedes simulation account")


def capture_unattested_checkpoint(*,account_ref,engine):
    """Atomic closure flush + state snapshot under the isolated account lock.

    A production runner MUST stop accepting orders after any failure. This
    function does not create, authorize or own that runner.
    """
    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        account=_account_locked(account_ref)
        _validate_account_engine(account,engine)
        flush_engine_closures(account_ref=account_ref,engine=engine)
        persisted,ledger_digest,ledger_seq=_load_closures(account)
        expected=engine.closed_execution_records
        if len(persisted)!=len(expected):
            raise JournalConflict("checkpoint and journal closure counts differ")
        for old,new in zip(expected,persisted):
            if old!=new:
                raise JournalConflict("checkpoint and journal closure contents differ")
        state=export_checkpoint(engine)
        payload={
            "schema":SCHEMA,"account_id":str(account.pk),"account_ref":account.account_ref,
            "policy_version":account.policy_version,
            "source_provenance":"unattested", "resumable":False,
            "journal_digest":ledger_digest,"journal_last_sequence":ledger_seq,
            "closure_count":len(persisted),"state":state,
        }
        encoded=_canonical(payload)
        digest=hashlib.sha256(encoded).hexdigest()
        event_ref="checkpoint:v1:"+digest
        events=PropSimulationEvent.objects.using(MOJPROP_DB_ALIAS).filter(account=account)
        old=events.filter(event_ref=event_ref).first()
        if old is not None:
            if (old.source!=SOURCE or old.event_type!=PropSimulationEvent.EventType.RISK
                    or old.payload_digest!=digest or old.payload!=payload):
                raise JournalConflict("checkpoint replay conflict")
            return old.sequence_no
        seq=(events.aggregate(high=Max("sequence_no"))["high"] or 0)+1
        PropSimulationEvent.objects.using(MOJPROP_DB_ALIAS).create(
            account_id=account.pk,event_ref=event_ref,sequence_no=seq,
            event_type=PropSimulationEvent.EventType.RISK,
            source=SOURCE,occurred_at=timezone.now(),payload_digest=digest,payload=payload)
        return seq


def inspect_checkpoint_after_restart(*,account_ref):
    """Read and restore the most recent snapshot, blocked even if healthy.

    Returns only a quarantined engine. An unrelated authenticated and
    journal-complete execution service would be needed for live resumption.
    """
    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        account=_account_locked(account_ref)
        event=(PropSimulationEvent.objects.using(MOJPROP_DB_ALIAS)
               .filter(account=account,event_type=PropSimulationEvent.EventType.RISK,source=SOURCE)
               .order_by("-sequence_no").first())
        if event is None:
            raise JournalConflict("no engine checkpoint available")
        p=event.payload
        if (type(p) is not dict or p.get("schema")!=SCHEMA
                or p.get("account_id")!=str(account.pk)
                or p.get("account_ref")!=account.account_ref
                or p.get("policy_version")!=account.policy_version
                or p.get("source_provenance")!="unattested"
                or p.get("resumable") is not False):
            raise JournalConflict("unsupported checkpoint or account mismatch")
        digest=hashlib.sha256(_canonical(p)).hexdigest()
        if digest!=event.payload_digest or event.event_ref!="checkpoint:v1:"+digest:
            raise JournalConflict("checkpoint digest invalid")
        persisted,ledger_digest,ledger_seq=_load_closures(account)
        if (p.get("journal_digest")!=ledger_digest
                or p.get("journal_last_sequence")!=ledger_seq
                or p.get("closure_count")!=len(persisted)):
            raise JournalConflict("journal changed since checkpoint")
        engine=recover_quarantined_engine(p["state"],closed_records=persisted)
        if engine.starting_balance!=account.starting_capital_usd:
            raise JournalConflict("restored capital mismatch")
        if engine.last_quote_time is not None and (account.opened_at is None
                or engine.last_quote_time<account.opened_at):
            raise JournalConflict("restored quote precedes account")
        return QuarantinedCheckpoint(engine,event.sequence_no,len(persisted),ledger_digest)
