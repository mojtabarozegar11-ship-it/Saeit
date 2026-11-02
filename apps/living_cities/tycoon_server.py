"""Server-authoritative endless business economy for Living Cities.

The client submits only intent. Server time, balances, unlocks, upgrades,
marketing boosts and idempotency are all enforced here. No blockchain
transaction or client-supplied payment receipt can credit Gems.
"""
import hashlib
import json
import math
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    PhysicalCodeClaim,
    PlayerTycoon,
    TycoonActionReceipt,
    TycoonMarketingReceipt,
)


BUSINESSES = {
    "bakery": (120, 2, 0),
    "cafe": (260, 5, 180),
    "tailor": (620, 12, 550),
    "bookshop": (1450, 28, 1300),
    "greenhouse": (3400, 65, 3000),
    "workshop": (7900, 150, 7000),
    "studio": (18000, 340, 16000),
    "delivery": (41000, 760, 36000),
    "hotel": (92000, 1700, 82000),
    "factory": (205000, 3800, 180000),
    "cinema": (460000, 8500, 400000),
    "laboratory": (1030000, 19000, 900000),
    "solar": (2300000, 42000, 2000000),
    "robotics": (5200000, 93000, 4500000),
    "airline": (11800000, 205000, 10000000),
    "media": (27000000, 450000, 23000000),
    "spaceport": (62000000, 1000000, 52000000),
    "orbital": (145000000, 2200000, 120000000),
    "quantum": (340000000, 4800000, 280000000),
    "starcity": (800000000, 10500000, 650000000),
}

CHARACTERS = {
    "nilo": (.10, 0),
    "mina": (.14, 500),
    "roshan": (.18, 2500),
    "ava": (.22, 9000),
    "navid": (.26, 30000),
    "laleh": (.30, 90000),
    "kian": (.35, 260000),
    "sara": (.40, 750000),
    "darya": (.46, 2200000),
    "arman": (.52, 7000000),
    "mahtab": (.60, 24000000),
    "shahin": (.70, 90000000),
}

GEM_PACKS = {
    "spark": {"gems": 100, "amount": 1, "symbol": "MOJ1", "network": "TRON"},
    "city": {"gems": 550, "amount": 5, "symbol": "MOJ1", "network": "TRON"},
    "world": {"gems": 1200, "amount": 10, "symbol": "MOJ1", "network": "TRON"},
}

OIL_CAPACITY = 24
MAX_OFFLINE_SECONDS = 8 * 60 * 60
MAX_VALUE = 1_000_000_000_000_000
MAX_CLOCK = 10_000_000_000
MAX_LEVEL = 1_000_000


def _require(condition, reason):
    if not condition:
        raise ValidationError(reason)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _initial():
    return {
        "version": 1,
        "clock": 0,
        "coins": 320,
        "gems": 0,
        "oil": 8,
        "lifetimeCoins": 0,
        "businessLevels": {key: 1 if key == "bakery" else 0 for key in BUSINESSES},
        "assignments": {},
        "marketingUntil": 0,
        "marketingReceipts": [],
        "gemReceipts": [],
    }


def _validate(state):
    _require(isinstance(state, dict) and state.get("version") == 1, "invalid_tycoon_state")
    _require(_number(state.get("clock")) and 0 <= state["clock"] <= MAX_CLOCK, "invalid_tycoon_clock")
    for key in ("coins", "oil", "lifetimeCoins", "marketingUntil"):
        _require(_number(state.get(key)) and 0 <= state[key] <= MAX_VALUE, "invalid_" + key)
    _require(type(state.get("gems")) is int and 0 <= state["gems"] <= MAX_VALUE, "invalid_gems")
    _require(state["oil"] <= OIL_CAPACITY, "invalid_oil")
    levels = state.get("businessLevels")
    _require(isinstance(levels, dict) and set(levels) == set(BUSINESSES), "invalid_business_catalog")
    _require(all(type(level) is int and 0 <= level <= MAX_LEVEL for level in levels.values()), "invalid_business_level")
    assignments = state.get("assignments")
    _require(isinstance(assignments, dict), "invalid_assignments")
    assigned = set()
    for business_id, character_id in assignments.items():
        _require(business_id in BUSINESSES and character_id in CHARACTERS, "unknown_assignment")
        _require(levels[business_id] > 0, "assignment_to_locked_business")
        _require(character_id not in assigned, "character_assigned_twice")
        _require(state["lifetimeCoins"] >= CHARACTERS[character_id][1], "locked_character_assigned")
        assigned.add(character_id)
    for key in ("marketingReceipts", "gemReceipts"):
        receipts = state.get(key)
        _require(isinstance(receipts, list) and len(receipts) <= 100, "invalid_receipts")
        _require(all(type(item) is int and item > 0 for item in receipts), "invalid_receipt")
        _require(len(receipts) == len(set(receipts)), "duplicate_receipt")
    return True


def _upgrade_cost(state, business_id):
    base_cost, _, _ = BUSINESSES[business_id]
    level = state["businessLevels"][business_id]
    if level > 190:
        return MAX_VALUE
    return min(MAX_VALUE, math.ceil(base_cost * (1.17 ** level)))


def _business_income(state, business_id):
    _, base_income, _ = BUSINESSES[business_id]
    level = state["businessLevels"][business_id]
    if level == 0:
        return 0
    level_bonus = 1 + ((level - 1) // 10) * .25
    character_id = state["assignments"].get(business_id)
    character_bonus = CHARACTERS[character_id][0] if character_id else 0
    return base_income * level * level_bonus * (1 + character_bonus)


def _income_rate(state):
    return sum(_business_income(state, business_id) for business_id in BUSINESSES)


def _advance(state, seconds):
    _validate(state)
    _require(_number(seconds) and seconds >= 0, "invalid_elapsed_time")
    elapsed = min(float(seconds), MAX_OFFLINE_SECONDS)
    if elapsed == 0:
        return state
    base_income = _income_rate(state)
    oil_seconds = min(elapsed, state["oil"] * 3600)
    marketing_seconds = min(elapsed, max(0, state["marketingUntil"] - state["clock"]))
    boundaries = sorted(set((0, elapsed, oil_seconds, marketing_seconds)))
    earned = 0
    for start, end in zip(boundaries, boundaries[1:]):
        if end <= start:
            continue
        midpoint = (start + end) / 2
        oil_multiplier = 1 if midpoint < oil_seconds else .4
        marketing_multiplier = 2 if midpoint < marketing_seconds else 1
        earned += base_income * (end - start) * oil_multiplier * marketing_multiplier
    state["clock"] = min(MAX_CLOCK, state["clock"] + elapsed)
    state["oil"] = max(0, state["oil"] - elapsed / 3600)
    state["coins"] = min(MAX_VALUE, state["coins"] + earned)
    state["lifetimeCoins"] = min(MAX_VALUE, state["lifetimeCoins"] + earned)
    _validate(state)
    return state


def _command(state, action):
    kind = action.get("type")
    _require(isinstance(kind, str) and len(kind) <= 32, "invalid_action")
    if kind == "upgrade":
        business_id = action.get("business_id")
        _require(isinstance(business_id, str) and business_id in BUSINESSES, "unknown_business")
        level = state["businessLevels"][business_id]
        _require(level < MAX_LEVEL, "business_level_limit")
        _require(level > 0 or state["lifetimeCoins"] >= BUSINESSES[business_id][2], "business_locked")
        cost = _upgrade_cost(state, business_id)
        _require(state["coins"] >= cost, "insufficient_coins")
        state["coins"] -= cost
        state["businessLevels"][business_id] += 1
    elif kind == "assign":
        character_id = action.get("character_id")
        business_id = action.get("business_id")
        _require(isinstance(character_id, str) and character_id in CHARACTERS, "unknown_character")
        _require(isinstance(business_id, str) and business_id in BUSINESSES, "unknown_business")
        _require(state["lifetimeCoins"] >= CHARACTERS[character_id][1], "character_locked")
        _require(state["businessLevels"][business_id] > 0, "business_not_owned")
        state["assignments"] = {
            assigned_business: assigned_character
            for assigned_business, assigned_character in state["assignments"].items()
            if assigned_character != character_id and assigned_business != business_id
        }
        state["assignments"][business_id] = character_id
    elif kind == "unassign":
        character_id = action.get("character_id")
        _require(isinstance(character_id, str) and character_id in CHARACTERS, "unknown_character")
        state["assignments"] = {
            business_id: assigned_character
            for business_id, assigned_character in state["assignments"].items()
            if assigned_character != character_id
        }
    elif kind == "refill_oil":
        _require(state["oil"] < OIL_CAPACITY, "oil_tank_full")
        cost = max(80, math.ceil(_income_rate(state) * 60))
        _require(state["coins"] >= cost, "insufficient_coins")
        state["coins"] -= cost
        state["oil"] = min(OIL_CAPACITY, state["oil"] + 6)
    elif kind == "gem_boost":
        _require(state["gems"] >= 15, "insufficient_gems")
        state["gems"] -= 15
        state["marketingUntil"] = max(state["clock"], state["marketingUntil"]) + 15 * 60
    else:
        raise ValidationError("unknown_tycoon_action")
    _validate(state)


def _load_locked(owner):
    model, _ = PlayerTycoon.objects.get_or_create(owner=owner, defaults={"payload": _initial()})
    return PlayerTycoon.objects.select_for_update().get(pk=model.pk)


def _advance_persisted(model, now):
    state = model.payload
    _validate(state)
    # Whole-second simulation keeps fresh snapshots deterministic and avoids
    # minting microscopic fractional coins from database/request latency.
    elapsed = min(MAX_OFFLINE_SECONDS, max(0, math.floor((now - model.last_simulated_at).total_seconds())))
    return _advance(state, elapsed) if elapsed else state


@transaction.atomic
def snapshot(owner):
    model = _load_locked(owner)
    now = timezone.now()
    state = _advance_persisted(model, now)
    if (now - model.last_simulated_at).total_seconds() >= 60:
        model.payload = state
        model.last_simulated_at = now
        model.save(update_fields=["payload", "last_simulated_at"])
    return {"state": state, "revision": model.revision, "authority": "server"}


@transaction.atomic
def act(owner, action, key):
    _require(isinstance(action, dict), "invalid_action")
    _require(isinstance(key, str) and re.fullmatch(r"[A-Za-z0-9_-]{16,96}", key), "invalid_action_key")
    try:
        canonical = json.dumps(action, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValidationError("invalid_action") from exc
    _require(len(canonical) <= 2048, "action_too_large")
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
    model = _load_locked(owner)
    receipt = TycoonActionReceipt.objects.filter(owner=owner, action_key=key).first()
    if receipt is not None:
        _require(receipt.action_digest == fingerprint, "idempotency_conflict")
        return {
            "state": _advance_persisted(model, timezone.now()),
            "revision": model.revision,
            "original_revision": receipt.revision,
            "authority": "server",
            "replayed": True,
        }
    now = timezone.now()
    state = _advance_persisted(model, now)
    _command(state, action)
    model.payload = state
    model.revision += 1
    model.last_simulated_at = now
    model.save(update_fields=["payload", "revision", "last_simulated_at"])
    TycoonActionReceipt.objects.create(
        owner=owner,
        action_key=key,
        action_digest=fingerprint,
        revision=model.revision,
    )
    return {"state": state, "revision": model.revision, "authority": "server", "replayed": False}


@transaction.atomic
def grant_product_marketing(owner, claim_id):
    _require(type(claim_id) is int and claim_id > 0, "invalid_claim")
    claim = PhysicalCodeClaim.objects.select_for_update().filter(
        pk=claim_id,
        claimant=owner,
        status="PENDING_POLICY",
    ).first()
    _require(claim is not None, "claim_not_eligible_for_marketing")
    model = _load_locked(owner)
    now = timezone.now()
    state = _advance_persisted(model, now)
    existing = TycoonMarketingReceipt.objects.filter(claim=claim).first()
    if existing is not None:
        return {
            "applied": False,
            "claim_id": claim.pk,
            "duration_seconds": existing.duration_seconds,
            "state": state,
            "revision": model.revision,
            "authority": "server",
        }
    next_revision = model.revision + 1
    TycoonMarketingReceipt.objects.create(
        owner=owner,
        claim=claim,
        duration_seconds=3600,
        revision=next_revision,
    )
    state["marketingReceipts"] = (state["marketingReceipts"] + [claim.pk])[-100:]
    state["marketingUntil"] = max(state["clock"], state["marketingUntil"]) + 3600
    _validate(state)
    model.payload = state
    model.revision = next_revision
    model.last_simulated_at = now
    model.save(update_fields=["payload", "revision", "last_simulated_at"])
    return {
        "applied": True,
        "claim_id": claim.pk,
        "duration_seconds": 3600,
        "state": state,
        "revision": model.revision,
        "authority": "server",
    }


def gem_pack(pack_id):
    _require(isinstance(pack_id, str) and pack_id in GEM_PACKS, "unknown_gem_pack")
    return {"pack_id": pack_id, **GEM_PACKS[pack_id]}
