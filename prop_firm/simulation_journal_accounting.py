"""Internal closure bridge and observed accounting summary.

No public endpoint, eligibility decision, market-data authentication or
payout authorization. The caller must bind the engine to an authenticated
account/session. A successful flush does not persist open positions or prove
complete execution history. A failed flush must stop that session and require
reconciliation before accepting more commands.
"""
from collections import defaultdict
from decimal import Decimal, Context, localcontext
from fractions import Fraction
from zoneinfo import ZoneInfo
from datetime import datetime

from django.db import transaction

from config.mojprop_db_router import MOJPROP_DB_ALIAS
from .models import PropSimulationAccount
from .simulation_engine import SimulationEngine
from .simulation_execution_journal import (
    JournalConflict, persist_closed_executions, read_closed_execution_payloads,
)


def flush_engine_closures(*, account_ref, engine):
    """Append complete current in-memory closure batch atomically.

    Repeating an identical flush returns the same journal sequence numbers.
    Chunk into bounded journal batches under one outer transaction. The
    entire history commits or rolls back together. A 10,000-record safety
    ceiling remains; longer sessions need a durable incremental checkpoint.
    """
    if type(engine) is not SimulationEngine:
        raise JournalConflict("internal simulation engine required")
    records=engine.closed_execution_records
    if len(records)!=engine.closed_trade_count:
        raise JournalConflict("engine closure count mismatch")
    if len(records)>10000:
        raise JournalConflict("bounded engine history exceeded")
    if any(type(r.net_pnl) is not Decimal or not r.net_pnl.is_finite()
           or len(r.net_pnl.as_tuple().digits)>38
           or abs(r.net_pnl.as_tuple().exponent)>30 for r in records):
        raise JournalConflict("invalid closure net profit")
    if type(engine.realized_pnl) is not Decimal or not engine.realized_pnl.is_finite():
        raise JournalConflict("invalid engine net profit")
    if sum((Fraction(r.net_pnl) for r in records),Fraction(0))!=engine.realized_pnl:
        raise JournalConflict("engine net profit mismatch")
    if len({r.order_id for r in records})!=len(records):
        raise JournalConflict("duplicate engine closure")
    if not records:
        return ()
    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        result=[]
        for start in range(0,len(records),500):
            result.extend(persist_closed_executions(
                account_ref=account_ref,records=records[start:start+500]))
        return tuple(result)


def observed_daily_accounting(*, account_ref, day_timezone):
    """Aggregate observed closed records under the caller's day convention.

    No absent date is treated as a verified zero. No trading-day policy is
    selected here. The account row lock follows the journal writer's lock
    convention to obtain a consistent bounded snapshot. No pass determination.
    """
    tz=ZoneInfo(day_timezone)
    if type(account_ref) is not str or not account_ref.strip() or len(account_ref)>96:
        raise JournalConflict("invalid account reference")
    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        account=PropSimulationAccount.objects.using(MOJPROP_DB_ALIAS).select_for_update().get(account_ref=account_ref)
        totals=defaultdict(lambda:Decimal("0"))
        count=0
        cursor=0
        seen=set()
        with localcontext(Context(prec=100)):
            while True:
                rows=read_closed_execution_payloads(account_ref=account.account_ref,after_sequence=cursor,limit=500)
                if not rows:
                    break
                if count+len(rows)>10000:
                    raise JournalConflict("bounded accounting review exceeded")
                for seq,p in rows:
                    if p["order_id"] in seen:
                        raise JournalConflict("duplicate observed order")
                    seen.add(p["order_id"])
                    dt=datetime.fromisoformat(p["closed_at"])
                    if dt.utcoffset() is None:
                        raise JournalConflict("invalid close timestamp")
                    net=Decimal(p["net_pnl"])
                    gross=Decimal(p["gross_pnl"])
                    commission=Decimal(p["commission"])
                    if not all(x.is_finite() for x in (net,gross,commission)) or commission<0 or gross-commission!=net:
                        raise JournalConflict("invalid persisted accounting")
                    totals[dt.astimezone(tz).date()]+=net
                    cursor=seq
                    count+=1
                if len(rows)<500:
                    break
            total=sum(totals.values(),Decimal("0"))
        return {"account_ref":account.account_ref,"day_timezone":tz.key,
                "observed_daily_net_usd":dict(sorted(totals.items())),
                "observed_net_usd":total,"observed_closures":count,
                "through_event_sequence":cursor,"provenance":"unattested",
                "complete_history_verified":False,"eligible_for_pass":False}
