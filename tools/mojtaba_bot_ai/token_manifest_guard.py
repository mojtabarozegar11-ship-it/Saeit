"""Read-only validation of the 51 planned token records. No deployment or wallet access."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

MOJONER_SUPPLY = 24_567_856
MIN_SUPPLY = 100_000_000_000
MAX_SUPPLY = 10_000_000_000_000
EXPECTED = {"Mojoner"} | {f"Moj{i}" for i in range(1, 51)}
BITCOIN_PROTOCOLS = {"runes", "rgb", "taproot-assets"}

def validate(records):
    errors = []
    if not isinstance(records, list):
        return ["root must be an array"]
    seen = set()
    for index, item in enumerate(records):
        key = f"records[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{key}: must be object")
            continue
        name = item.get("name")
        if not isinstance(name, str) or name not in EXPECTED:
            errors.append(f"{key}: unknown or invalid token name")
            continue
        if name in seen:
            errors.append(f"{key}: duplicate {name}")
        seen.add(name)
        supply = item.get("total_supply")
        if isinstance(supply, bool) or not isinstance(supply, int):
            errors.append(f"{name}: total_supply must be integer (not float/bool)")
        elif name == "Mojoner" and supply != MOJONER_SUPPLY:
            errors.append(f"{name}: must have exactly {MOJONER_SUPPLY} units")
        elif name != "Mojoner" and not MIN_SUPPLY <= supply <= MAX_SUPPLY:
            errors.append(f"{name}: supply outside approved range")
        network = item.get("network")
        protocol = item.get("protocol")
        if name == "Mojoner":
            if network != "bitcoin":
                errors.append("Mojoner: network must be bitcoin")
            if protocol not in BITCOIN_PROTOCOLS:
                errors.append("Mojoner: bitcoin protocol must be explicitly evaluated")
        elif not isinstance(network, str) or not network.strip() or network.lower() == "bitcoin":
            errors.append(f"{name}: independent non-bitcoin network required")
        if not isinstance(protocol, str) or not protocol.strip():
            errors.append(f"{name}: protocol required")
        # A manifest is a proposal, never an owner authorization.
        if item.get("deployed") is True:
            errors.append(f"{name}: deployed=true cannot be established by a manifest")
        if item.get("owner_approved") is True:
            errors.append(f"{name}: approval requires separate verifiable owner evidence")
    missing = sorted(EXPECTED - seen, key=lambda x: (x != "Mojoner", int(x[3:]) if re.fullmatch(r"Moj[0-9]+", x) else 0))
    if missing:
        errors.append("missing: " + ", ".join(missing))
    return errors

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        records = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Cannot read manifest: {exc}\n")
    errors = validate(records)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0

if __name__ == "__main__":
    raise SystemExit(main())
