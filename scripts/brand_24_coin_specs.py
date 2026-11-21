#!/usr/bin/env python3
"""Generate and verify ONLY private, offline Shasta TRC-20 source specifications.

No network access, transactions, wallet access, public website writes, or deploy.
Compatible with scripts/factory_f41_token_builder_v2.py.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "factory_config/f41_brand_24_coin_registry_20261113.json"
EXPECTED_BRANDS = (
    "saman", "zahra", "zhila", "marzieh", "maryam", "marjan",
    "mohammad", "mostafa", "farnaz", "faremah", "taniya", "raham",
)
ROOT_FIELDS = {
    "schema", "created_utc", "stage", "owner_scope", "standard",
    "prototype_network", "mainnet_network", "decimals", "deployment",
    "release_gates", "brands",
}
TOKEN_FIELDS = {
    "role", "name", "symbol", "proposed_supply_tokens",
    "contract_address", "deployment_txid", "status",
}
BRAND_FIELDS = {"brand_slug", "brand_fa", "tokens"}
SAFE_MODES = ("service_learning", "community_game")
EXPECTED_SUPPLY = {"service_learning": "1000000000", "community_game": "100000000"}


def _no_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("DUPLICATE_JSON_KEY")
        obj[key] = value
    return obj


def read_registry(path=DEFAULT_REGISTRY):
    source = Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 65536:
        raise ValueError("UNTRUSTED_BRAND_REGISTRY")
    return json.loads(source.read_text("utf-8"), object_pairs_hook=_no_duplicate_keys)


def validate_registry(data):
    if type(data) is not dict or set(data) != ROOT_FIELDS:
        raise ValueError("BAD_REGISTRY_ROOT")
    if (data["schema"] != "saeit.brand-24-coins.registry.v1"
        or data["stage"] != "OFFLINE_PROPOSAL_NOT_ISSUED"
        or data["standard"] != "TRC-20"
        or data["prototype_network"] != "shasta"
        or data["mainnet_network"] is not None
        or type(data["decimals"]) is not int or data["decimals"] != 18):
        raise ValueError("UNAUTHORIZED_CHAIN_OR_STAGE")
    switches = data["deployment"]
    if type(switches) is not dict or set(switches) != {
        "mainnet_enabled", "testnet_broadcast_enabled", "public_sale_enabled",
        "liquidity_enabled", "payments_performed", "revenue_verified"
    } or any(value is not False for value in switches.values()):
        raise ValueError("DEPLOYMENT_AND_PAYMENT_MUST_REMAIN_DISABLED")
    if not isinstance(data["release_gates"], list) or len(data["release_gates"]) < 6:
        raise ValueError("INSUFFICIENT_RELEASE_GATES")
    items = data["brands"]
    if not isinstance(items, list) or len(items) != 12:
        raise ValueError("EXPECTED_TWELVE_BRANDS")
    seen_names, seen_symbols, seen_brands = set(), set(), set()
    output = {}
    for brand in items:
        if type(brand) is not dict or set(brand) != BRAND_FIELDS:
            raise ValueError("BAD_BRAND_FIELDS")
        slug = brand["brand_slug"]
        if slug not in EXPECTED_BRANDS or slug in seen_brands:
            raise ValueError("DUPLICATE_OR_UNKNOWN_BRAND")
        seen_brands.add(slug)
        if not isinstance(brand["brand_fa"], str) or not brand["brand_fa"].strip():
            raise ValueError("MISSING_BRAND_NAME")
        tokens = brand["tokens"]
        if not isinstance(tokens, list) or len(tokens) != 2:
            raise ValueError("EXPECTED_TWO_COINS_PER_BRAND")
        seen_roles = set()
        for token in tokens:
            if type(token) is not dict or set(token) != TOKEN_FIELDS:
                raise ValueError("BAD_TOKEN_FIELDS")
            role, name, symbol = token["role"], token["name"], token["symbol"]
            if role not in SAFE_MODES or role in seen_roles:
                raise ValueError("INVALID_ROLE_PAIR")
            seen_roles.add(role)
            if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ]{2,47}", name)
                or not isinstance(symbol, str) or not re.fullmatch(r"ZM[A-Z0-9]{4}", symbol)):
                raise ValueError("BAD_NAME_OR_SYMBOL")
            if name in seen_names or symbol in seen_symbols:
                raise ValueError("DUPLICATE_TOKEN_IDENTITY")
            seen_names.add(name)
            seen_symbols.add(symbol)
            if (token["proposed_supply_tokens"] != EXPECTED_SUPPLY[role]
                or token["contract_address"] is not None
                or token["deployment_txid"] is not None
                or token["status"] != "offline_spec_only"):
                raise ValueError("NON_OFFLINE_OR_UNAPPROVED_TOKEN")
            spec = {
                "schema": "saeit.factory.f41-token-spec.v1",
                "name": name, "symbol": symbol,
                "supply_tokens": token["proposed_supply_tokens"],
                "decimals": 18, "network": "shasta",
                "standard": "TRC-20", "mode": "fixed_supply",
            }
            output[f"{slug}-{role}.json"] = (json.dumps(
                spec, ensure_ascii=False, sort_keys=True, indent=2
            ) + "\n").encode("utf-8")
    if seen_brands != set(EXPECTED_BRANDS) or len(output) != 24:
        raise ValueError("REGISTRY_INCOMPLETE")
    return output


def verify_specs(registry, directory):
    expected = validate_registry(registry)
    dest = Path(directory)
    if dest.is_symlink() or not dest.is_dir():
        raise ValueError("OUTPUT_FOLDER_INVALID")
    found = {p.name for p in dest.iterdir()}
    if found != set(expected):
        raise ValueError("OUTPUT_FILE_INVENTORY_MISMATCH")
    for name, content in expected.items():
        path = dest / name
        if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
            raise ValueError("OUTPUT_SPEC_MISMATCH:" + name)
    return len(expected)


def write_specs(registry, directory):
    expected = validate_registry(registry)
    dest = Path(directory)
    if dest.exists() or dest.is_symlink() or dest.parent.is_symlink() or not dest.parent.is_dir():
        raise ValueError("OUTPUT_DESTINATION_MUST_BE_NEW")
    dest.mkdir(mode=0o700)
    for name, content in expected.items():
        path = dest / name
        with path.open("xb") as handle:
            handle.write(content)
        path.chmod(0o600)
    return verify_specs(registry, dest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--out", help="New private folder for 24 offline Shasta specs")
    selection.add_argument("--verify", help="Existing folder of 24 previously generated specs")
    args = parser.parse_args()
    data = read_registry(args.registry)
    if args.out:
        count = write_specs(data, args.out)
    elif args.verify:
        count = verify_specs(data, args.verify)
    else:
        count = len(validate_registry(data))
    print("BRAND_COUNT=12")
    print(f"OFFLINE_SPEC_COUNT={count}")
    print("CHAIN_TRANSACTIONS=0")
    print("MAINNET_DEPLOYMENT=false")
    print("COIN_ISSUANCE_VERIFIED=false")
    print("REVENUE_VERIFIED=false")


if __name__ == "__main__":
    main()
