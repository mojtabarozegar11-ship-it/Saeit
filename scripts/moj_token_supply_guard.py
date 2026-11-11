#!/usr/bin/env python3
"""Read-only, fail-closed validation of a proposed Moj token manifest. No RPC or deployment."""
import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

MOJONER_SUPPLY = 24567856
LOWER, UPPER = 100_000_000_000, 10_000_000_000_000
TOKEN_IDS = {"Mojoner"} | {f"Moj{i}" for i in range(1, 51)}
BITCOIN_PROTOCOLS = {"runes", "taproot-assets", "rgb"}

def validate(manifest):
    errors = []
    if not isinstance(manifest, dict) or not isinstance(manifest.get("tokens"), list):
        return ["Manifest must contain a tokens array"]
    entries = manifest["tokens"]
    seen = set()
    for idx, item in enumerate(entries):
        prefix = f"tokens[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: expected object")
            continue
        name = item.get("id")
        if not isinstance(name, str) or name not in TOKEN_IDS:
            errors.append(f"{prefix}: unknown token id")
            continue
        if name in seen:
            errors.append(f"{prefix}: duplicate {name}")
        seen.add(name)
        supply = item.get("total_supply")
        if isinstance(supply, bool) or not isinstance(supply, (str, int)):
            errors.append(f"{name}: supply must be integer string or integer")
            continue
        if not re.fullmatch(r"[0-9]+", str(supply)):
            errors.append(f"{name}: supply must be a positive whole number")
            continue
        value = int(supply)
        if name == "Mojoner":
            if value != MOJONER_SUPPLY:
                errors.append("Mojoner: total supply must equal 24567856")
            if item.get("network") != "bitcoin":
                errors.append("Mojoner: network must be bitcoin")
            if item.get("protocol") not in BITCOIN_PROTOCOLS:
                errors.append("Mojoner: select documented Bitcoin asset protocol")
        else:
            if not LOWER <= value <= UPPER:
                errors.append(f"{name}: total supply outside allowed range")
            if not isinstance(item.get("network"), str) or not item["network"].strip() or item["network"].lower() == "bitcoin":
                errors.append(f"{name}: explicit non-Bitcoin network required")
            if not isinstance(item.get("protocol"), str) or not item["protocol"].strip():
                errors.append(f"{name}: explicit protocol required")
        if item.get("owner_approved") is not True:
            errors.append(f"{name}: case-specific owner approval missing")
        if not isinstance(item.get("approval_reference"), str) or not item["approval_reference"].strip():
            errors.append(f"{name}: approval reference missing")
    for missing in sorted(TOKEN_IDS - seen):
        errors.append(f"{missing}: missing token entry")
    if len(entries) != 51:
        errors.append(f"Expected exactly 51 entries, got {len(entries)}")
    return errors

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"INVALID: {exc}\n")
    errors = validate(data)
    if errors:
        for err in errors:
            print("BLOCK:", err)
        return 1
    print("VALIDATED: 51 entries and explicit owner approvals; this is NOT a deployment authorization.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
