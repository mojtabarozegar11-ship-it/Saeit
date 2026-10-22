#!/usr/bin/env python3
"""Bounded read-only finality sidecar for moj_1ro_1's existing F41 AgentTask queue.

Must run *after* factory_f41_enqueue --execute under its existing master lock.
Never changes Django tasks, customer delivery, stores, or wallet balances.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import factory_f41_multi_product_builder as builder
import factory_f41_shasta_finality as finality

ORDER = re.compile(r"F41-[a-z0-9-]{3,56}\Z")
MAX_ORDERS = 64
MAX_ACTIVE_PER_CYCLE = 4
MAX_TX_PER_ORDER = 2


def _dir(path):
    p = Path(path)
    if p.is_symlink() or not p.is_dir():
        raise ValueError("F41_AUTOSCAN_UNSAFE_DIRECTORY")
    return p


def _proof_valid(path, spec):
    """An immutable proof folder can be reused only if its bytes remain intact."""
    _dir(path)
    files = list(path.iterdir())
    if len(files) != 2 or {f.name for f in files} != {"finality.json", "manifest.json"}:
        raise ValueError("F41_AUTOSCAN_PROOF_INVENTORY_CHANGED")
    for p in files:
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 150000:
            raise ValueError("F41_AUTOSCAN_PROOF_FILE_UNTRUSTED")
    manifest = json.loads((path / "manifest.json").read_text("utf8"))
    report = json.loads((path / "finality.json").read_text("utf8"))
    if (type(manifest) is not dict or type(report) is not dict
            or manifest.get("schema") != "saeit.factory.f41-finality-evidence.v1"
            or manifest.get("finality_sha256") != finality.checksum(finality.canonical(report))
            or manifest.get("spec_sha256") != finality.checksum(builder.enc(spec))
            or manifest.get("customer_delivery_enabled") is not False
            or manifest.get("signed_attestation") is not False
            or report.get("simulation_used") is not False
            or report.get("customer_delivery_enabled") is not False
            or report.get("original_request_sha256") != finality.checksum(builder.enc(spec))):
        raise ValueError("F41_AUTOSCAN_PROOF_DIGEST_OR_POLICY_CHANGED")
    return report


def scan(queue, outputs, assets, proofs, *, now=None, execute=False, issue=finality.write_private):
    queue, outputs, assets, proofs = (_dir(p) for p in (queue, outputs, assets, proofs))
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("F41_AUTOSCAN_TIMEZONE_REQUIRED")
    now = now.astimezone(timezone.utc)
    cycle = now.strftime("%Y%m%dT%H") + ("%02d" % ((now.minute // 15) * 15))
    entries = sorted(queue.iterdir())
    if len(entries) > MAX_ORDERS:
        raise ValueError("F41_AUTOSCAN_QUEUE_SIZE_LIMIT")
    eligible = []
    counters = {"scanned": len(entries), "reconciliation_orders": 0,
                "pilot_skipped": 0, "output_pending": 0,
                "cost_limited": 0, "proofs_created": 0,
                "idempotent": 0, "verified_invoices": 0}
    for path in entries:
        if (path.is_symlink() or not path.is_file() or path.stat().st_size > 150000
                or not ORDER.fullmatch(path.stem) or path.suffix != ".json"):
            raise ValueError("F41_AUTOSCAN_UNTRUSTED_QUEUE_ENTRY")
        spec = builder.read_request(path)
        if spec["kind"] != "reconciliation":
            continue
        counters["reconciliation_orders"] += 1
        # Pilot/mock invoice IDs never contribute to apparent live-payment metrics.
        if spec["product_id"] == "merchant_receipts_demo":
            counters["pilot_skipped"] += 1
            continue
        previous = outputs / path.stem
        if not previous.exists():
            counters["output_pending"] += 1
            continue
        if previous.is_symlink():
            raise ValueError("F41_AUTOSCAN_PRODUCT_SYMLINK")
        receipt = builder.verify(path, previous, assets)
        if receipt.get("quality_1000_certified") is not False:
            raise ValueError("F41_AUTOSCAN_SOURCE_PRODUCT_POLICY_CHANGED")
        if len(spec["data"]["observations"]) > MAX_TX_PER_ORDER:
            counters["cost_limited"] += 1
            continue
        eligible.append((path, spec))
    # Fair rotation across more than four work orders avoids permanent starvation.
    if eligible:
        shift = (int(now.timestamp()) // 900) % len(eligible)
        eligible = eligible[shift:] + eligible[:shift]
    # Maximum eight RPCs at ten seconds each stays under the 130s cron window.
    for path, spec in eligible[:MAX_ACTIVE_PER_CYCLE]:
        target = proofs / (path.stem + "-" + cycle)
        if target.is_symlink():
            raise ValueError("F41_AUTOSCAN_PROOF_SYMLINK")
        if target.exists():
            result = _proof_valid(target, spec)
            counters["idempotent"] += 1
            counters["verified_invoices"] += result["verified_match_count"]
            continue
        if execute:
            result = issue(path, target)
            if result.get("customer_delivery_enabled") is not False or result.get("simulation_used") is not False:
                raise ValueError("F41_AUTOSCAN_RELEASE_OR_SIMULATION_POLICY_FAILURE")
            _proof_valid(target, spec)
            counters["proofs_created"] += 1
            counters["verified_invoices"] += result["verified_match_count"]
    counters["deferred_due_to_cycle_cap"] = max(0, len(eligible) - MAX_ACTIVE_PER_CYCLE)
    counters["financial_actions"] = 0
    counters["customer_delivery_enabled"] = False
    return counters


def main():
    ap = argparse.ArgumentParser()
    modes = ap.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    base = Path.home() / "factory-runtime"
    cycle = base / "private" / "autonomous-product-cycle"
    ops = base / "operations" / "f41-multiproduct"
    proof = cycle / "f41-solidity-finality" / "automatic"
    result = scan(cycle / "f41-multiproduct" / "orders",
                  cycle / "f41-multiproduct" / "outputs",
                  ops / "assets", proof, execute=args.execute)
    print("F41_MOJ1RO1_AUTOMATIC_FINALITY=" + ("ACTIVE" if args.execute else "DRY_RUN_PASS"))
    for key, value in result.items():
        print("F41_FINALITY_" + key.upper() + "=" + str(value).lower())


if __name__ == "__main__":
    main()
