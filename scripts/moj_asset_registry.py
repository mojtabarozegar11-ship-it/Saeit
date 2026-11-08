#!/usr/bin/env python3
"""Deterministic, offline issuance *planning* for Mojoner and Moj1..Moj50.

No wallet, RPC client, signing, broadcast, deployment or revenue mechanism is
present.  A candidate is NOT an issued token or an investment product.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "saeit.moj.asset-program.v1"
MOJONER_SUPPLY = 24_567_856
MIN_SERIES_SUPPLY = 100_000_000_000
MAX_SERIES_SUPPLY = 10_000_000_000_000
SERIES_SIZE = 50
F41_SCHEMA = "saeit.factory.f41-token-spec.v1"


def series_supply(number: int) -> int:
    """An explicit, revisable proposal across the owner's stated range.

    Supplies increase in whole billions, with both endpoints included.
    No on-chain or commercial decision is implied.
    """
    if type(number) is not int or not 1 <= number <= SERIES_SIZE:
        raise ValueError("invalid_moj_index")
    billion = 1_000_000_000
    return (100 + (9_900 * (number - 1)) // (SERIES_SIZE - 1)) * billion


def generate_program() -> dict:
    assets = [{
        "id": "mojoner", "name": "Mojoner", "symbol_candidate": "MOJONER",
        "network": "bitcoin", "protocol_candidate": "runes",
        "supply_tokens": str(MOJONER_SUPPLY), "supply_status": "owner_specified",
        "divisibility_proposal": 0,
        "runes_etching_proposal": {"premine": str(MOJONER_SUPPLY),
                                   "mint_amount": "0", "mint_cap": "0"},
        "name_availability_verified": False,
        "issuance_state": "not_issued", "mainnet_authorized": False,
    }]
    for number in range(1, SERIES_SIZE + 1):
        assets.append({
            "id": f"moj{number}", "name": f"Moj {number}",
            "symbol_candidate": f"MOJ{number}",
            "network": "undecided_non_bitcoin",
            "protocol_candidate": "undecided",
            "supply_tokens": str(series_supply(number)),
            "supply_status": "revisable_proposal_within_owner_range",
            "decimals": None, "issuance_state": "not_issued",
            "mainnet_authorized": False,
        })
    manifest = {
        "schema": SCHEMA, "purpose": "offline_preissuance_planning",
        "assets": assets,
        "commercial_release_authorized": False,
        "wallet_or_private_key_required": False,
        "transactions_broadcast": 0,
        "verified_income": "0",
        "gates": {
            "owner_fee_approval": False, "chain_and_protocol_selection": False,
            "independent_security_review": False,
            "legal_and_marketing_review": False,
            "liquidity_and_market_risk_review": False,
        },
    }
    validate_program(manifest)
    return manifest


def _whole_number(value: object) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*", value):
        raise ValueError("supply_must_be_positive_integer_string")
    return int(value)


def validate_program(program: dict) -> None:
    """Fail closed on oversupply, identifier collisions and false launch claims."""
    if not isinstance(program, dict) or program.get("schema") != SCHEMA:
        raise ValueError("invalid_program_schema")
    assets = program.get("assets")
    if not isinstance(assets, list) or len(assets) != SERIES_SIZE + 1:
        raise ValueError("wrong_asset_count")
    ids = [item.get("id") for item in assets if isinstance(item, dict)]
    symbols = [item.get("symbol_candidate") for item in assets if isinstance(item, dict)]
    if len(ids) != len(assets) or len(set(ids)) != len(assets) or len(set(symbols)) != len(assets):
        raise ValueError("asset_identifier_collision")
    bitcoin = assets[0]
    if (bitcoin.get("id") != "mojoner" or bitcoin.get("network") != "bitcoin"
            or bitcoin.get("protocol_candidate") != "runes"
            or bitcoin.get("symbol_candidate") != "MOJONER"
            or bitcoin.get("supply_status") != "owner_specified"
            or _whole_number(bitcoin.get("supply_tokens")) != MOJONER_SUPPLY
            or type(bitcoin.get("divisibility_proposal")) is not int
            or bitcoin["divisibility_proposal"] != 0
            or bitcoin.get("name_availability_verified") is not False):
        raise ValueError("bitcoin_runes_spec_mismatch")
    terms = bitcoin.get("runes_etching_proposal")
    if (not isinstance(terms, dict)
            or _whole_number(terms.get("premine")) != MOJONER_SUPPLY
            or terms.get("mint_amount") != "0" or terms.get("mint_cap") != "0"):
        raise ValueError("runes_supply_formula_mismatch")
    last = 0
    for number, asset in enumerate(assets[1:], start=1):
        supply = _whole_number(asset.get("supply_tokens"))
        if (asset.get("id") != f"moj{number}"
                or asset.get("name") != f"Moj {number}"
                or asset.get("symbol_candidate") != f"MOJ{number}"
                or asset.get("network") != "undecided_non_bitcoin"
                or asset.get("protocol_candidate") != "undecided"
                or asset.get("decimals", "missing") is not None
                or asset.get("supply_status") != "revisable_proposal_within_owner_range"
                or supply != series_supply(number)
                or not MIN_SERIES_SUPPLY <= supply <= MAX_SERIES_SUPPLY
                or supply <= last):
            raise ValueError("series_asset_spec_mismatch")
        last = supply
    if (any(item.get("issuance_state") != "not_issued"
            or item.get("mainnet_authorized") is not False for item in assets)
            or program.get("commercial_release_authorized") is not False
            or program.get("wallet_or_private_key_required") is not False
            or type(program.get("transactions_broadcast")) is not int
            or program["transactions_broadcast"] != 0
            or program.get("verified_income") != "0"):
        raise ValueError("unverified_issuance_or_income_claim")
    gates = program.get("gates")
    if (not isinstance(gates, dict) or set(gates) != {
            "owner_fee_approval", "chain_and_protocol_selection",
            "independent_security_review", "legal_and_marketing_review",
            "liquidity_and_market_risk_review"}
            or any(value is not False for value in gates.values())):
        raise ValueError("unauthorized_release_gate")


def f41_shasta_candidate_specs(program: dict) -> dict[str, dict]:
    """Feed the existing F41 *offline* TRC-20 generator, not a mainnet chain."""
    validate_program(program)
    return {
        asset["id"]: {
            "schema": F41_SCHEMA, "name": asset["name"],
            "symbol": asset["symbol_candidate"],
            "supply_tokens": asset["supply_tokens"], "decimals": 18,
            "network": "shasta", "standard": "TRC-20", "mode": "fixed_supply",
        }
        for asset in program["assets"][1:]
    }


def export_bundle(program: dict, target: Path, *, include_f41: bool = True) -> dict:
    """Write exactly one new offline bundle; never replace prior user data."""
    validate_program(program)
    if target.is_symlink() or target.exists() or not target.parent.is_dir():
        raise ValueError("output_must_be_new_directory")
    target.mkdir(mode=0o700)
    try:
        docs = {"asset-program.json": program}
        if include_f41:
            docs.update({f"f41-shasta/{name}.json": spec
                         for name, spec in f41_shasta_candidate_specs(program).items()})
        checksums = {}
        for name, obj in docs.items():
            path = target / name
            path.parent.mkdir(exist_ok=True)
            data = (json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
            with path.open("xb") as stream:
                stream.write(data)
            checksums[name] = hashlib.sha256(data).hexdigest()
        with (target / "SHA256SUMS.json").open("x", encoding="utf-8") as stream:
            json.dump(checksums, stream, indent=2, sort_keys=True)
            stream.write("\n")
        return {"assets": len(program["assets"]), "offline_files": len(docs) + 1,
                "sha256": checksums, "on_chain_issuance": False}
    except BaseException:
        # Retain failed intermediate output for inspection, never overwrite.
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="new offline output directory")
    parser.add_argument("--no-f41", action="store_true")
    args = parser.parse_args()
    program = generate_program()
    if args.out:
        receipt = export_bundle(program, args.out, include_f41=not args.no_f41)
        print(json.dumps({"assets": receipt["assets"], "offline_files": receipt["offline_files"],
                          "on_chain_issuance": False}, sort_keys=True))
    else:
        print(json.dumps(program, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
