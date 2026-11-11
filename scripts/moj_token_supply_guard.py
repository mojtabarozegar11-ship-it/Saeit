#!/usr/bin/env python3
"""Fail-closed supply registry validator. No minting, signing, RPC or deployments."""
import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

MOJONER_SUPPLY = 24_567_856
MIN_SUPPLY = 100_000_000_000
MAX_SUPPLY = 10_000_000_000_000
EXPECTED_IDS = {"Mojoner"} | {f"Moj{i}" for i in range(1, 51)}


def validate(data):
    if not isinstance(data, dict) or set(data) != EXPECTED_IDS:
        raise ValueError("registry must contain exactly Mojoner and Moj1..Moj50")
    for name, entry in data.items():
        if not isinstance(entry, dict):
            raise ValueError(f"{name}: expected object")
        value = entry.get("total_supply")
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError(f"{name}: supply must be an integer or decimal string")
        try:
            number = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"{name}: invalid supply") from exc
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError(f"{name}: supply must be finite whole units")
        if name == "Mojoner":
            if number != MOJONER_SUPPLY or entry.get("network") != "bitcoin":
                raise ValueError("Mojoner requires exactly 24567856 units on bitcoin")
        elif not MIN_SUPPLY <= number <= MAX_SUPPLY:
            raise ValueError(f"{name}: supply outside approved range")
        if entry.get("approved") is not True:
            raise ValueError(f"{name}: explicit per-token approval is required")
        if not isinstance(entry.get("protocol"), str) or not entry["protocol"].strip():
            raise ValueError(f"{name}: documented protocol selection required")
        if not isinstance(entry.get("network"), str) or not entry["network"].strip():
            raise ValueError(f"{name}: network selection required")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    args = parser.parse_args()
    try:
        validate(json.loads(args.registry.read_text(encoding="utf-8")))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"NOT APPROVED: {exc}\n")
    print("Registry constraints passed; NOT authorization to mint, deploy or sell.")


if __name__ == "__main__":
    main()
