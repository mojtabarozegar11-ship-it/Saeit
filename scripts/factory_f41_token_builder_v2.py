#!/usr/bin/env python3
"""Offline F41 fixed-supply TRC-20 kit maker: NO network, key, deploy or sale."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

SCHEMA = "saeit.factory.f41-token-spec.v1"
RECEIPT = "saeit.factory.f41-private-candidate.v1"
FIELDS = {"schema", "name", "symbol", "supply_tokens", "decimals",
          "network", "standard", "mode"}
FILES = ("contracts/FactoryFixedSupplyToken.sol", "package.json",
         "tronbox-config.js", "README.md", "quality-obligations.json")


def encoded(item):
    return (json.dumps(item, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def spec_read(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 4096:
        raise ValueError("F41_UNTRUSTED_SPEC")
    obj = json.loads(p.read_text(encoding="utf8"))
    if not isinstance(obj, dict) or set(obj) != FIELDS:
        raise ValueError("F41_SPEC_FIELDS")
    if (obj["schema"] != SCHEMA or obj["network"] != "shasta"
            or obj["standard"] != "TRC-20" or obj["mode"] != "fixed_supply"):
        raise ValueError("F41_TESTNET_FIXED_SUPPLY_ONLY")
    if not isinstance(obj["name"], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ]{2,47}", obj["name"]):
        raise ValueError("F41_BAD_NAME")
    if not isinstance(obj["symbol"], str) or not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", obj["symbol"]):
        raise ValueError("F41_BAD_SYMBOL")
    if type(obj["decimals"]) is not int or obj["decimals"] != 18:
        raise ValueError("F41_DECIMALS_POLICY")
    count = obj["supply_tokens"]
    if not isinstance(count, str) or not re.fullmatch(r"[1-9][0-9]{0,38}", count):
        raise ValueError("F41_SUPPLY_INTEGER_STRING")
    units = int(count) * 10 ** 18
    if units > 2 ** 256 - 1:
        raise ValueError("F41_UINT256_OVERFLOW")
    return obj, units


def outputs(spec, units):
    source = ("""// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;
import {TRC20} from "@openzeppelin/tron-contracts/token/TRC20/TRC20.sol";
// Shasta-only private candidate. No owner, upgrade or post-deploy mint.
contract FactoryFixedSupplyToken is TRC20 {
    constructor() TRC20("%s", "%s") {
        _mint(msg.sender, %d);
    }
}
""" % (spec["name"], spec["symbol"], units)).encode("utf8")
    package = {
        "name": "saeit-f41-trc20-private-candidate", "version": "0.1.0",
        "private": True, "dependencies": {
            "@openzeppelin/tron-contracts": "5.6.0", "tronweb": "6.5.0"},
        "devDependencies": {"tronbox": "4.10.0"},
        "overrides": {"diff": "8.0.3", "serialize-javascript": "7.0.5",
                      "ws": "8.21.0", "tronbox": {"tronweb": "6.5.0"}}
    }
    config = ("module.exports = { compilers: { solc: { version: '0.8.20', "
              "settings: { optimizer: { enabled: true, runs: 200 } } } } };\n")
    notes = """# F41 blockchain and token production line

This immutable source kit is only for offline private Shasta testing.
No key or deployment script is included; no tokens have been issued.
The entire fixed supply is allocated to a manual test deployer by constructor.
Install pinned dependencies with npm and compile with npx tronbox compile.
Before ANY issuance, independently audit runtime transfer/allowance behavior,
reproducible compilation, supply limits, TRON Energy and tokenomics.
Require legal analysis and explicit owner authorization for mainnet/sales.
Generation 100 and QA1000 are targets, NOT earned or certified.
"""
    quality = {
        "schema": "saeit.factory.f41-quality-obligations.v1",
        "target_generation": 100, "verified_generation": 0,
        "quality_policy": "factory_config/active_quality_1000_policy.json",
        "required_quality_groups": 100, "required_points": 1000,
        "independently_verified_points": None,
        "independent_specialist_approved": False,
        "commercial_release_allowed": False,
        "owner_approval_required": True,
        "criteria": [{"id": "Q%03d" % i,
                      "status": "awaiting_independent_measurement",
                      "approved_points": 0} for i in range(1, 101)]
    }
    return {
        FILES[0]: source,
        FILES[1]: encoded(package),
        FILES[2]: config.encode("utf8"),
        FILES[3]: notes.encode("utf8"),
        FILES[4]: encoded(quality)
    }


def expected_manifest(spec, units, blobs):
    return {
        "schema": RECEIPT, "line_id": "F41",
        "network": "shasta", "standard": "TRC-20",
        "name": spec["name"], "symbol": spec["symbol"], "decimals": 18,
        "token_supply": spec["supply_tokens"],
        "total_supply_base_units": str(units),
        "spec_sha256": digest(encoded(spec)),
        "files_sha256": {n: digest(v) for n, v in blobs.items()},
        "generation_100_verified": False, "verified_generation": 0,
        "quality_1000_certified": False, "independent_audit": False,
        "production_deployment_enabled": False, "commercial_release": False,
        "transaction_broadcasts": 0, "site_writes": 0
    }


def verify(spec_path, folder):
    spec, units = spec_read(spec_path)
    base = Path(folder)
    if base.is_symlink() or not base.is_dir():
        raise ValueError("F41_CANDIDATE_INVALID")
    names = set()
    for p in base.rglob("*"):
        if p.is_symlink():
            raise ValueError("F41_UNTRUSTED_SYMLINK")
        if p.is_file():
            names.add(p.relative_to(base).as_posix())
    if names != set(FILES) | {"manifest.json"}:
        raise ValueError("F41_FILE_INVENTORY_MISMATCH")
    blobs = outputs(spec, units)
    receipt = json.loads((base / "manifest.json").read_text("utf8"))
    if receipt != expected_manifest(spec, units, blobs):
        raise ValueError("F41_RECEIPT_MISMATCH")
    for name, blob in blobs.items():
        if (base / name).read_bytes() != blob:
            raise ValueError("F41_ARTIFACT_TAMPERED:" + name)
    return receipt


def build(spec_path, folder):
    spec, units = spec_read(spec_path)
    dest = Path(folder)
    if dest.parent.is_symlink() or not dest.parent.is_dir() or dest.exists() or dest.is_symlink():
        raise ValueError("F41_REQUIRES_NEW_DESTINATION")
    stage = Path(tempfile.mkdtemp(prefix=".f41-staging-", dir=str(dest.parent)))
    try:
        os.chmod(str(stage), 0o700)
        blobs = outputs(spec, units)
        for name, blob in blobs.items():
            file = stage / name
            file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with file.open("xb") as stream:
                stream.write(blob)
            os.chmod(str(file), 0o600)
        manifest = expected_manifest(spec, units, blobs)
        (stage / "manifest.json").write_bytes(encoded(manifest))
        os.chmod(str(stage / "manifest.json"), 0o600)
        os.rename(str(stage), str(dest))
    except BaseException:
        if stage.exists():
            shutil.rmtree(str(stage))
        raise
    return verify(spec_path, dest)


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--spec", required=True)
    cli.add_argument("--out", required=True)
    cli.add_argument("--verify", action="store_true")
    args = cli.parse_args()
    receipt = verify(args.spec, args.out) if args.verify else build(args.spec, args.out)
    print("F41_SOURCE_SHA256=" + receipt["files_sha256"][FILES[0]])
    print("F41_SHASTA_PRIVATE_BUILD=PASS")
    print("F41_GENERATION_100_VERIFIED=false")
    print("F41_QUALITY_1000_CERTIFIED=false")
    print("F41_COMMERCIAL_RELEASE=false")
