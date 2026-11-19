"""Server-owned simulation event ledger. No market or brokerage connection is supplied here."""
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from dataclasses import asdict
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac, constant_time_compare
from .models import PropSimulationAccount, PropSimulationEvent
from .simulation_engine import SimulationEngine, MarketQuote, OrderRequest
from .simulation_identity import is_verified_simulation_user
from .simulation_fulfillment import verified_simulation_purchase

VERSION = "simulation-engine-v1"
ROOT = "0" * 64

def _signing_key():
    key = getattr(settings, "MPW_SIMULATION_EVENT_KEY", "")
    if not isinstance(key, str) or len(key) < 32:
        raise ValidationError("Durable event signing key required")
    return key

def _digest(account_id, sequence, command_id, prior, payload):
    canonical = json.dumps([str(account_id), sequence, str(command_id), prior, payload],
                           sort_keys=True, separators=(",", ":"), allow_nan=False)
    return salted_hmac("mojprop.execution.events.v1", canonical,
                       secret=_signing_key(), algorithm="sha256").hexdigest()

def _quote_payload(q):
    if not isinstance(q, MarketQuote):
        raise ValidationError("Server-owned quote required")
    return {"symbol": q.symbol, "bid": str(q.bid), "ask": str(q.ask),
            "timestamp": q.timestamp, "sequence": q.sequence}

def _order_payload(order):
    if not isinstance(order, OrderRequest):
        raise ValidationError("Order required")
    data = asdict(order)
    for key, value in data.items():
        if isinstance(value, Decimal):
            data[key] = str(value)
    return data

def _apply(engine, payload):
    if payload.get("version") != VERSION:
        raise ValidationError("Unsupported historical execution version")
    q = MarketQuote(**(payload["quote"] | {"bid": Decimal(payload["quote"]["bid"]),
                                          "ask": Decimal(payload["quote"]["ask"])}))
    operation = payload["operation"]
    if operation == "quote":
        return engine.process_quote(q)
    if operation == "close":
        return engine.close(payload["order_id"], q)
    if operation == "submit":
        order = dict(payload["order"])
        for key in ("quantity", "limit_price", "stop_price", "stop_loss", "take_profit"):
            if order[key] is not None:
                order[key] = Decimal(order[key])
        return engine.submit(OrderRequest(**order), q)
    raise ValidationError("Unknown historical operation")

def _locked_account(account_id, owner):
    if not is_verified_simulation_user(owner):
        raise ValidationError("Verified customer required")
    account = PropSimulationAccount.objects.select_for_update().filter(
        pk=account_id, owner=owner, invoice__simulation_owner__owner=owner).first()
    if account is None:
        raise ValidationError("Account unavailable")
    verified_simulation_purchase(invoice_id=account.invoice_id, buyer_email=owner.email)
    if account.starting_balance_usd != 1000 or account.challenge_days != 60:
        raise ValidationError("Unexpected immutable challenge parameters")
    return account

def _replay(account):
    engine = SimulationEngine(starting_balance=account.starting_balance_usd)
    prior = ROOT
    sequence = 0
    for event in account.execution_events.order_by("sequence").iterator(chunk_size=500):
        sequence += 1
        if (event.sequence != sequence or event.prior_digest != prior
                or not constant_time_compare(event.digest, _digest(account.pk, sequence,
                    event.command_id, prior, event.payload))):
            raise ValidationError("Simulation execution ledger integrity failure")
        _apply(engine, event.payload)
        prior = event.digest
    if account.event_head_sequence != sequence or not constant_time_compare(account.event_head_digest, prior):
        raise ValidationError("Simulation execution ledger head mismatch")
    return engine, sequence, prior

@transaction.atomic
def account_snapshot(*, account_id, owner):
    account = _locked_account(account_id, owner)
    engine, _, _ = _replay(account)
    return engine.snapshot()

@transaction.atomic
def record_command(*, account_id, owner, command_id, operation, order=None, order_id=None):
    """Only an internal service may resolve quotes. Browser-supplied prices never enter."""
    if getattr(settings, "MPW_SIMULATION_TRADING_ENABLED", False) is not True:
        raise ValidationError("Trading service is unavailable")
    resolver = getattr(settings, "MPW_SIMULATION_QUOTE_PROVIDER", None)
    if not callable(resolver):
        raise ValidationError("Approved server quote provider required")
    _signing_key()
    try:
        command_id = uuid.UUID(str(command_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Invalid command ID") from exc
    account = _locked_account(account_id, owner)
    if (account.status != "active"
            or timezone.now() >= account.created_at + timedelta(days=account.challenge_days)):
        raise ValidationError("Challenge is closed or expired")
    engine, sequence, prior = _replay(account)
    action = {"operation": operation, "version": VERSION}
    if operation == "submit":
        action["order"] = _order_payload(order)
        symbol = order.symbol
    elif operation == "close":
        previous = account.execution_events.filter(command_id=command_id).first()
        action["order_id"] = order_id
        if previous is not None:
            if {k:v for k,v in previous.payload.items() if k != "quote"} != action:
                raise ValidationError("Conflicting command reuse")
            return engine.snapshot()
        position = engine.positions.get(order_id)
        if position is None:
            raise ValidationError("Position unavailable")
        symbol = position.symbol
    else:
        raise ValidationError("Unsupported customer command")
    event = account.execution_events.filter(command_id=command_id).first()
    if event is not None:
        if {k:v for k,v in event.payload.items() if k != "quote"} != action:
            raise ValidationError("Conflicting command reuse")
        return engine.snapshot()
    quote = resolver(account_id=account.pk, symbol=symbol)
    if not isinstance(quote, MarketQuote) or quote.symbol != symbol:
        raise ValidationError("Authoritative quote unavailable")
    payload = action | {"quote": _quote_payload(quote)}
    _apply(engine, payload)
    sequence += 1
    _append_event(account, sequence, command_id, prior, payload)
    return engine.snapshot()


def _append_event(account, sequence, command_id, prior, payload):
    digest = _digest(account.pk, sequence, command_id, prior, payload)
    PropSimulationEvent.objects.create(account=account, sequence=sequence,
        command_id=command_id, prior_digest=prior, payload=payload, digest=digest)
    account.event_head_sequence = sequence
    account.event_head_digest = digest
    account.save(update_fields=["event_head_sequence", "event_head_digest"])


@transaction.atomic
def advance_account_quotes(*, account_id):
    """Internal scheduled processor; caller cannot supply market prices."""
    if getattr(settings, "MPW_SIMULATION_TRADING_ENABLED", False) is not True:
        raise ValidationError("Trading service unavailable")
    resolver = getattr(settings, "MPW_SIMULATION_QUOTE_PROVIDER", None)
    if not callable(resolver):
        raise ValidationError("Approved quote provider required")
    account = PropSimulationAccount.objects.select_for_update().select_related("owner").get(pk=account_id)
    _locked_account(account.pk, account.owner)
    if account.status != "active" or timezone.now() >= account.created_at + timedelta(days=account.challenge_days):
        raise ValidationError("Challenge closed or expired")
    engine, sequence, prior = _replay(account)
    symbols = sorted({item.symbol for item in engine.positions.values()} |
                     {item.symbol for item in engine.pending.values()})
    for symbol in symbols:
        quote = resolver(account_id=account.pk, symbol=symbol)
        if not isinstance(quote, MarketQuote) or quote.symbol != symbol:
            raise ValidationError("Authoritative quote unavailable")
        if quote.sequence <= engine.last_quote_sequence:
            continue
        payload = {"operation": "quote", "version": VERSION, "quote": _quote_payload(quote)}
        _apply(engine, payload)
        sequence += 1
        _append_event(account, sequence, uuid.uuid4(), prior, payload)
        prior = account.event_head_digest
    return engine.snapshot()


@transaction.atomic
def terminal_state(*, account_id, owner):
    account = _locked_account(account_id, owner)
    engine, _, _ = _replay(account)
    return {
        "summary": engine.snapshot(),
        "positions": list(engine.positions.values()),
        "pending": list(engine.pending.values()),
        "recent_closed": list(engine.closed[-20:][::-1]),
        "expires_at": account.created_at + timedelta(days=account.challenge_days),
        "active": account.status == "active" and not engine.blocked and
                  timezone.now() < account.created_at + timedelta(days=account.challenge_days),
    }
