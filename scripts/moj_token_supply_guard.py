#!/usr/bin/env python3
"""Offline pre-deployment inventory gate; never broadcasts or deploys tokens.

Usage: python scripts/moj_token_supply_guard.py manifest.json
A passing result is NOT owner authorization, legal clearance or security audit.
"""
import json
import re
import sys
from pathlib import Path

MIN_SUPPLY = 100_000_000_000
MAX_SUPPLY = 10_000_000_000_000
MOJONER_SUPPLY = 24_567_856
IDS = {"Mojoner"} | {f"Moj{i}" for i in range(1, 51)}
ALLOWED_STATES = {"undecided", "research", "review", "approved"}

def check_manifest(data):
    errors = []
    if not isinstance(data, dict) or not isinstance(data.get("tokens"), list):
        return ["Root must contain a tokens array."]
    tokens = data["tokens"]
    names = [t.get("id") for t in tokens if isinstance(t, dict)]
    if any(not isinstance(name, str) for name in names):
        return ["Every token ID must be a string."]
    if len(tokens) != 51:
        errors.append(f"Expected 51 entries, got {len(tokens)}.")
    if len(names) != len(tokens) or len(names) != len(set(names)):
        errors.append("Entries must be objects with unique IDs.")
    missing, extra = IDS - set(names), set(names) - IDS
    if missing:
        errors.append("Missing IDs: " + ", ".join(sorted(missing)))
    if extra:
        errors.append("Unexpected IDs: " + ", ".join(sorted(map(str, extra))))
    for t in tokens:
        if not isinstance(t, dict):
            continue
        name = t.get("id")
        supply = t.get("total_supply")
        if isinstance(supply, bool) or not isinstance(supply, int):
            errors.append(f"{name}: total_supply must be an exact integer (not float/string/bool).")
        elif name == "Mojoner" and supply != MOJONER_SUPPLY:
            errors.append("Mojoner: total_supply must equal 24567856.")
        elif name != "Mojoner" and name in IDS and not MIN_SUPPLY <= supply <= MAX_SUPPLY:
            errors.append(f"{name}: supply outside 100 billion to 10 trillion.")
        if name == "Mojoner" and t.get("chain") != "bitcoin":
            errors.append("Mojoner: chain must be bitcoin.")
        if name != "Mojoner" and t.get("chain") == "bitcoin":
            errors.append(f"{name}: must use a non-Bitcoin chain.")
        if t.get("status") not in ALLOWED_STATES:
            errors.append(f"{name}: invalid status.")
        if t.get("status") == "approved":
            # A local JSON file cannot authenticate a person's consent.
            errors.append(f"{name}: 'approved' in a manifest is NOT verified owner consent.")
        if not isinstance(t.get("protocol"), str) or not t["protocol"].strip():
            errors.append(f"{name}: protocol must be explicitly documented, including 'undecided'.")
        if not isinstance(t.get("chain"), str) or not t["chain"].strip():
            errors.append(f"{name}: chain must be documented, including 'undecided' for Moj1-Moj50.")
    return errors

def main(argv):
    if len(argv) != 2:
        print("Usage: moj_token_supply_guard.py manifest.json", file=sys.stderr)
        return 2
    try:
        data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        errors = check_manifest(data)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Invalid manifest: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print("FAIL:", error, file=sys.stderr)
        return 1
    print("PASS: inventory/supply consistency only. Deployment and spending remain BLOCKED.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
