#!/usr/bin/env python3
"""F41 multi-product PRIVATE blockchain utility factory. No payments, keys, or network."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

SCHEMA = "saeit.factory.f41-product-request.v1"
RECEIPT = "saeit.factory.f41-multiproduct-receipt.v1"
TYPES = {
    "vesting": "Deterministic tokenomics and treasury vesting schedule",
    "reconciliation": "Fail-closed merchant crypto payment reconciliation",
    "provenance": "Digital-asset SHA256 integrity and provenance inventory",
    "nft_metadata": "NFT collection metadata with media byte integrity"
}
SAFE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{1,63}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
TX = re.compile(r"[A-Fa-f0-9]{64}\Z")


def enc(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def positive(value, max_digits=38):
    if type(value) is not str or not re.fullmatch(r"(?:0|[1-9][0-9]{0,%d})" % (max_digits-1), value):
        raise ValueError("F41_INVALID_INTEGER_STRING")
    return int(value)


def read_request(path):
    p = Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size > 150000:
        raise ValueError("F41_REQUEST_NOT_TRUSTED")
    spec = json.loads(p.read_text("utf8"))
    if (type(spec) is not dict or set(spec) != {"schema", "kind", "product_id", "data"}
            or spec["schema"] != SCHEMA or spec["kind"] not in TYPES
            or type(spec["product_id"]) is not str or not SAFE.fullmatch(spec["product_id"])
            or type(spec["data"]) is not dict):
        raise ValueError("F41_REQUEST_FIELDS")
    return spec


def rows_csv(rows):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    for row in rows:
        writer.writerow(row)
    return out.getvalue().encode("utf8")


def vesting(data):
    if set(data) != {"total_supply", "months", "allocations"}:
        raise ValueError("F41_VESTING_FIELDS")
    total = positive(data["total_supply"])
    months = data["months"]
    allocations = data["allocations"]
    if (total < 1 or type(months) is not int or not 1 <= months <= 120
            or type(allocations) is not list or not 1 <= len(allocations) <= 30):
        raise ValueError("F41_VESTING_BOUNDS")
    observed = set()
    ledger = []
    allocated = 0
    for entry in allocations:
        if type(entry) is not dict or set(entry) != {"bucket", "amount", "start_month", "duration_months"}:
            raise ValueError("F41_ALLOCATION_FIELDS")
        bucket = entry["bucket"]
        amount = positive(entry["amount"])
        start = entry["start_month"]
        duration = entry["duration_months"]
        if (type(bucket) is not str or not SAFE.fullmatch(bucket) or bucket in observed
                or amount == 0 or type(start) is not int or type(duration) is not int
                or start < 1 or duration < 1 or start + duration - 1 > months):
            raise ValueError("F41_ALLOCATION_INVALID")
        observed.add(bucket)
        allocated += amount
        # Floor division and last-period remainder: exact whole-unit conservation.
        step, rem = divmod(amount, duration)
        for m in range(start, start + duration):
            value = step + (rem if m == start + duration - 1 else 0)
            ledger.append((m, bucket, value))
    if allocated > total:
        raise ValueError("F41_ALLOCATION_EXCEEDS_SUPPLY")
    ledger.sort()
    result = [["month", "bucket", "unlocked_base_units"]] + [[m, b, v] for m, b, v in ledger]
    return {
        "vesting.csv": rows_csv(result),
        "model.json": enc({
            "total_supply": str(total), "allocated": str(allocated),
            "unallocated": str(total - allocated), "months": months,
            "rows": len(ledger), "sum_unlocked": str(sum(t[2] for t in ledger)),
            "market_price_estimate": None, "financial_outcome_guaranteed": False})
    }


def reconciliation(data):
    if set(data) != {"invoices", "observations"}:
        raise ValueError("F41_RECONCILIATION_FIELDS")
    invoices, observations = data["invoices"], data["observations"]
    if (type(invoices) is not list or type(observations) is not list
            or not 1 <= len(invoices) <= 500 or len(observations) > 2000):
        raise ValueError("F41_RECONCILIATION_SIZE")
    expected = {}
    for inv in invoices:
        if type(inv) is not dict or set(inv) != {"id", "network", "asset", "recipient", "amount_base_units"}:
            raise ValueError("F41_INVOICE_FIELDS")
        ident = inv["id"]
        if (type(ident) is not str or not SAFE.fullmatch(ident) or ident in expected
                or inv["network"] != "shasta" or inv["asset"] not in ("TRX", "TRC20")
                or type(inv["recipient"]) is not str or not re.fullmatch(r"T[1-9A-HJ-NP-Za-km-z]{33}", inv["recipient"])
                or positive(inv["amount_base_units"]) < 1):
            raise ValueError("F41_BAD_INVOICE")
        expected[ident] = inv
    by_invoice = {i: [] for i in expected}
    used_txs = set()
    for obs in observations:
        if type(obs) is not dict or set(obs) != {"invoice_id", "txid", "network", "asset", "recipient", "amount_base_units", "node_receipt_sha256"}:
            raise ValueError("F41_OBSERVATION_FIELDS")
        txid = obs["txid"]
        if (type(txid) is not str or not TX.fullmatch(txid)
                or txid in used_txs or obs["invoice_id"] not in expected
                or type(obs["node_receipt_sha256"]) is not str
                or not HEX.fullmatch(obs["node_receipt_sha256"])):
            raise ValueError("F41_DUPLICATE_OR_INVALID_OBSERVATION")
        used_txs.add(txid)
        positive(obs["amount_base_units"])
        by_invoice[obs["invoice_id"]].append(obs)
    report = []
    for ident in sorted(expected):
        inv = expected[ident]
        hits = by_invoice[ident]
        if not hits:
            status = "NO_OBSERVATION"
        elif len(hits) != 1:
            status = "MULTIPLE_TRANSACTIONS_MANUAL_REVIEW"
        elif any(hits[0][field] != inv[field] for field in ("network", "asset", "recipient", "amount_base_units")):
            status = "MISMATCH_MANUAL_REVIEW"
        else:
            # A SHA supplied by an untrusted source is not independent blockchain proof.
            status = "MATCHED_INPUT_AWAITING_INDEPENDENT_SOLIDITY_NODE_VERIFICATION"
        report.append({"invoice_id": ident, "status": status,
                       "observation_count": len(hits), "delivery_authorized": False})
    return {
        "reconciliation.json": enc({
            "network": "shasta", "records": report,
            "observation_hashes": [sha(enc(x)) for x in observations],
            "chain_finality_independently_verified": False,
            "customer_delivery_enabled": False,
            "transactions_broadcast": 0}),
        "reconciliation.csv": rows_csv(
            [["invoice_id", "status", "delivery_authorized"]] +
            [[r["invoice_id"], r["status"], "false"] for r in report])
    }


def read_asset(root, filename):
    if root is None:
        raise ValueError("F41_ASSET_ROOT_REQUIRED")
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("F41_ASSET_ROOT_UNSAFE")
    if type(filename) is not str or not SAFE.fullmatch(filename):
        raise ValueError("F41_BAD_ASSET_NAME")
    file = root / filename
    if not file.is_file() or file.is_symlink() or file.stat().st_size > 10_000_000:
        raise ValueError("F41_ASSET_FILE_UNSAFE")
    return file.read_bytes()


def provenance(data, asset_root):
    if set(data) != {"files", "claimed_license"} or type(data["files"]) is not list:
        raise ValueError("F41_PROVENANCE_FIELDS")
    names = data["files"]
    if not 1 <= len(names) <= 100 or len(set(names)) != len(names):
        raise ValueError("F41_PROVENANCE_FILE_COUNT")
    if type(data["claimed_license"]) is not str or not re.fullmatch(r"[A-Za-z0-9 ._-]{2,80}", data["claimed_license"]):
        raise ValueError("F41_LICENSE_LABEL_INVALID")
    manifest = []
    for name in sorted(names):
        blob = read_asset(asset_root, name)
        manifest.append({"file": name, "sha256": sha(blob), "bytes": len(blob)})
    return {"provenance.json": enc({
        "assets": manifest, "claimed_license": data["claimed_license"],
        "rights_authentication": "UNVERIFIED_OWNER_CLAIM",
        "blockchain_registered": False, "legal_title_certified": False})}


def nft_metadata(data, asset_root):
    if set(data) != {"collection", "items"} or type(data["items"]) is not list:
        raise ValueError("F41_NFT_FIELDS")
    if type(data["collection"]) is not str or not re.fullmatch(r"[A-Za-z0-9 ]{3,60}", data["collection"]):
        raise ValueError("F41_NFT_COLLECTION_INVALID")
    items = data["items"]
    if not 1 <= len(items) <= 100:
        raise ValueError("F41_NFT_ITEMS_RANGE")
    ids, result, checks = set(), {}, []
    for row in items:
        if type(row) is not dict or set(row) != {"token_id", "name", "media_file"}:
            raise ValueError("F41_NFT_ITEM_FIELDS")
        tid, name = row["token_id"], row["name"]
        if (type(tid) is not int or tid < 1 or tid > 100000000 or tid in ids
                or type(name) is not str or not re.fullmatch(r"[A-Za-z0-9 ._-]{2,64}", name)):
            raise ValueError("F41_NFT_ID_NAME")
        ids.add(tid)
        blob = read_asset(asset_root, row["media_file"])
        checks.append({"token_id": tid, "media_file": row["media_file"],
                       "sha256": sha(blob), "bytes": len(blob)})
        # Asset URI is local-only: IPFS pinning, token mint and marketplace listing NOT done.
        result["metadata/%d.json" % tid] = enc({
            "name": name, "description": data["collection"] + " private candidate",
            "image": "asset://sha256/" + sha(blob),
            "attributes": [{"trait_type": "collection", "value": data["collection"]}]})
    result["collection-manifest.json"] = enc({
        "collection": data["collection"], "items": sorted(checks, key=lambda x: x["token_id"]),
        "ipfs_pinning_completed": False, "trc721_minted": False,
        "marketplace_listed": False, "copyright_verified": False})
    return result


def payload(spec, asset_root):
    mode, data = spec["kind"], spec["data"]
    if mode == "vesting":
        return vesting(data)
    if mode == "reconciliation":
        return reconciliation(data)
    if mode == "provenance":
        return provenance(data, asset_root)
    return nft_metadata(data, asset_root)


def manifest(spec, files):
    return {
        "schema": RECEIPT, "line_id": "F41", "kind": spec["kind"],
        "product_id": spec["product_id"], "request_sha256": sha(enc(spec)),
        "file_sha256": {name: sha(data) for name, data in files.items()},
        "technical_build": True,
        "candidate_only": True, "generated_asset_count": len(files),
        "target_generation": 100, "generation_100_achieved": False,
        "quality_1000_certified": False, "independent_domain_review": False,
        "commercial_readiness": "PENDING_REAL_CUSTOMER_AND_LEGAL_GATES",
        "liquidity_guaranteed": False, "real_revenue_usd": None,
        "owner_commercial_approval": False, "transaction_broadcast_count": 0,
        "site_writes": 0, "financial_actions": 0
    }


def verify(spec_path, out, asset_root=None):
    spec = read_request(spec_path)
    folder = Path(out)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("F41_OUTPUT_DIRECTORY_UNSAFE")
    expected = payload(spec, asset_root)
    wanted = manifest(spec, expected)
    actual = json.loads((folder / "manifest.json").read_text("utf8"))
    if actual != wanted:
        raise ValueError("F41_MANIFEST_INTEGRITY_FAILED")
    actual_files = set()
    for p in folder.rglob("*"):
        if p.is_symlink():
            raise ValueError("F41_OUTPUT_SYMLINK")
        if p.is_file():
            actual_files.add(p.relative_to(folder).as_posix())
    if actual_files != set(expected) | {"manifest.json"}:
        raise ValueError("F41_INVENTORY_MISMATCH")
    for name, blob in expected.items():
        if (folder / name).read_bytes() != blob:
            raise ValueError("F41_PRODUCT_BYTES_MISMATCH:" + name)
    return wanted


def build(spec_path, out, asset_root=None):
    spec = read_request(spec_path)
    dst = Path(out)
    if dst.is_symlink() or dst.exists() or not dst.parent.is_dir() or dst.parent.is_symlink():
        raise ValueError("F41_OUTPUT_MUST_BE_NEW")
    blobs = payload(spec, asset_root)
    stage = Path(tempfile.mkdtemp(prefix=".f41-product-", dir=str(dst.parent)))
    try:
        os.chmod(str(stage), 0o700)
        for name, data in blobs.items():
            file = stage / name
            file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with file.open("xb") as fh:
                fh.write(data)
            os.chmod(str(file), 0o600)
        (stage / "manifest.json").write_bytes(enc(manifest(spec, blobs)))
        os.chmod(str(stage / "manifest.json"), 0o600)
        os.rename(str(stage), str(dst))
    except BaseException:
        if stage.exists():
            shutil.rmtree(str(stage))
        raise
    return verify(spec_path, dst, asset_root)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--assets")
    ap.add_argument("--verify", action="store_true")
    opts = ap.parse_args()
    receipt = verify(opts.spec, opts.out, opts.assets) if opts.verify else build(opts.spec, opts.out, opts.assets)
    print("F41_REAL_PRIVATE_PRODUCT=" + receipt["kind"])
    print("F41_MANIFEST_SHA256=" + sha(enc(receipt)))
    print("F41_EXTERNAL_QUALITY_CERTIFIED=false")
    print("F41_MARKET_LIQUIDITY_PROVEN=false")
