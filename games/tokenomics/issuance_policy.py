"""Offline issuance arithmetic for Mojoner and the Moj1–Moj50 proposals.

No wallet operations, chain deployment, price promises, or network assumptions.
"""
from decimal import Decimal, InvalidOperation
import re

MOJONER_TOTAL = 24_567_856
MIN_OTHER = 100_000_000_000
MAX_OTHER = 10_000_000_000_000


def token_name(value: str) -> str:
    if value == "Mojoner" or (
        isinstance(value, str)
        and re.fullmatch(r"Moj(?:[1-9]|[1-4][0-9]|50)", value)
    ):
        return value
    raise ValueError("unrecognized token identifier")


def exact_supply(name: str, amount: object) -> int:
    name = token_name(name)
    if isinstance(amount, bool):
        raise ValueError("boolean supply forbidden")
    raw = str(amount)
    if len(raw) > 64 or not re.fullmatch(r"[0-9]+", raw):
        raise ValueError("supply must be an unsigned decimal integer")
    try:
        parsed = Decimal(raw)
    except (InvalidOperation, ValueError):
        raise ValueError("invalid supply") from None
    if not parsed.is_finite() or parsed != parsed.to_integral_value():
        raise ValueError("supply must be an exact integer")
    value = int(parsed)
    if name == "Mojoner":
        if value != MOJONER_TOTAL:
            raise ValueError("Mojoner fixed issuance mismatch")
    elif not MIN_OTHER <= value <= MAX_OTHER:
        raise ValueError("independent token outside authorized issuance range")
    return value


def allocate(name: str, supply: object, allocations: dict[str, object]) -> dict[str, int]:
    total = exact_supply(name, supply)
    if not isinstance(allocations, dict) or not allocations:
        raise ValueError("nonempty allocations required")
    normalized = {}
    for bucket, quantity in allocations.items():
        if not isinstance(bucket, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", bucket):
            raise ValueError("invalid allocation bucket")
        normalized[bucket] = exact_nonnegative(quantity)
    if sum(normalized.values()) != total:
        raise ValueError("allocations must equal fixed total, without inflation")
    return normalized


def exact_nonnegative(amount: object) -> int:
    if isinstance(amount, bool):
        raise ValueError("boolean allocation forbidden")
    raw = str(amount)
    if len(raw) > 64 or not re.fullmatch(r"[0-9]+", raw):
        raise ValueError("allocation must be an unsigned decimal integer")
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        raise ValueError("invalid allocation") from None
    if not value.is_finite() or value < 0 or value != value.to_integral_value():
        raise ValueError("allocation must be nonnegative integer")
    return int(value)


def release_gate(name: str, supply: object, network: str | None, owner_approved: bool) -> bool:
    exact_supply(name, supply)
    if not network or not isinstance(network, str) or not network.strip():
        raise ValueError("network is unresolved")
    if name == "Mojoner" and network != "Bitcoin":
        raise ValueError("Mojoner must use Bitcoin-based protocol")
    if name != "Mojoner" and network == "Bitcoin":
        raise ValueError("other tokens require another blockchain")
    if owner_approved is not True:
        raise PermissionError("case-specific owner approval required")
    return True
