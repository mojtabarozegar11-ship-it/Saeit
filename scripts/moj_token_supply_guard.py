#!/usr/bin/env python3
"""Offline, fail-closed supply and approval gate for the 51 proposed MOJ tokens.

Input JSON: {"tokens":[{"id":"Mojoner","chain":"bitcoin","protocol":"...",
"total_supply":"24567856","owner_approval_id":"..."}, ...]}.
This script never signs, deploys, broadcasts or spends funds.
"""
import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

EXPECTED = {"Mojoner"} | {f"Moj{i}" for i in range(1, 51)}
MIN_SUPPLY = Decimal("100000000000")
MAX_SUPPLY = Decimal("10000000000000")


def validate(payload):
    errors = []
    tokens = payload.get("tokens")
    if not isinstance(tokens, list):
        return ["tokens must be an array"]
    seen = set()
    for index, token in enumerate(tokens):
        if not isinstance(token, dict):
            errors.append(f"tokens[{index}]: expected object")
            continue
        name = token.get("id")
        if not isinstance(name, str) or name not in EXPECTED:
            errors.append(f"tokens[{index}]: unexpected token id")
            continue
        if name in seen:
            errors.append(f"{name}: duplicate id")
        seen.add(name)
        raw = token.get("total_supply")
        if not isinstance(raw, str) or not re.fullmatch(r"[0-9]+", raw):
            errors.append(f"{name}: supply must be an integer decimal string")
        else:
            try:
                supply = Decimal(raw)
                if name == "Mojoner" and supply != Decimal("24567856"):
                    errors.append("Mojoner: exact supply must be 24567856")
                if name != "Mojoner" and not MIN_SUPPLY <= supply <= MAX_SUPPLY:
                    errors.append(f"{name}: supply outside 100B..10T")
            except InvalidOperation:
                errors.append(f"{name}: invalid supply")
        chain = token.get("chain")
        protocol = token.get("protocol")
        approval = token.get("owner_approval_id")
        if not isinstance(chain, str) or not chain.strip():
            errors.append(f"{name}: chain is not selected")
        if name == "Mojoner" and chain != "bitcoin":
            errors.append("Mojoner: chain must be bitcoin")
        if not isinstance(protocol, str) or not protocol.strip():
            errors.append(f"{name}: protocol is not selected")
        if not isinstance(approval, str) or not approval.strip():
            errors.append(f"{name}: owner-specific approval is missing")
    missing = EXPECTED - seen
    if missing:
        errors.append(f"missing token ids: {', '.join(sorted(missing))}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        errors = validate(data) if isinstance(data, dict) else ["root must be an object"]
    except (OSError, ValueError) as exc:
        errors = [f"manifest cannot be read: {exc}"]
    if errors:
        for error in errors:
            print("BLOCKED:", error)
        raise SystemExit(1)
    print("VALID: 51 identifiers and supply/approval fields; independent legal/security review still required")


if __name__ == "__main__":
    main()
