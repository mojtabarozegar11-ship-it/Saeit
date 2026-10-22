#!/usr/bin/env python3
"""F41 Merchant Audit: reproducible offline invoice/export reconciliation.

This is an ACCOUNTING candidate, not a blockchain finality oracle or a payment gateway.
No network, wallet, key, payment, delivery or public-site interaction is performed.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

SCHEMA = "saeit.f41.merchant-audit.v1"
INV_FIELDS = ["invoice_id", "network", "asset", "recipient", "amount_base_units", "token_contract"]
PAY_FIELDS = ["invoice_id", "txid", "network", "asset", "recipient", "amount_base_units", "token_contract"]
ALLOWED_NETWORKS = {"shasta", "tron-mainnet"}
HEX64 = re.compile(r"[0-9a-fA-F]{64}\Z")
SAFE_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{1,63}\Z")
AMOUNT = re.compile(r"[1-9][0-9]{0,37}\Z")
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
MAX_BYTES = 2_000_000


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def tron_address(address):
    """Check Base58Check and TRON 0x41 prefix, not only T/length."""
    if not isinstance(address, str) or len(address) != 34 or not address.startswith("T"):
        return False
    number = 0
    for char in address:
        if char not in B58:
            return False
        number = number * 58 + B58.index(char)
    body = number.to_bytes((number.bit_length() + 7) // 8, "big")
    body = b"\x00" * (len(address) - len(address.lstrip("1"))) + body
    return (len(body) == 25 and body[0] == 0x41 and
            hashlib.sha256(hashlib.sha256(body[:21]).digest()).digest()[:4] == body[21:])


def input_bytes(path):
    p = Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size > MAX_BYTES:
        raise ValueError("F41_UNSAFE_INPUT")
    content = p.read_bytes()
    if len(content) > MAX_BYTES or b"\x00" in content:
        raise ValueError("F41_UNSAFE_INPUT_BYTES")
    return content


def read_csv(content, fields, maximum):
    try:
        source = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(source, newline=""), strict=True)
        if reader.fieldnames != fields:
            raise ValueError("F41_CSV_SCHEMA")
        rows = []
        for row in reader:
            if len(rows) >= maximum or None in row or any(type(row[k]) is not str for k in fields):
                raise ValueError("F41_CSV_ROW_INVALID")
            rows.append(row)
    except (UnicodeDecodeError, csv.Error) as err:
        raise ValueError("F41_CSV_DECODE") from err
    return rows


def validate_record(row, payment):
    ident = row["invoice_id"]
    if not SAFE_ID.fullmatch(ident):
        raise ValueError("F41_ID_INVALID")
    if row["network"] not in ALLOWED_NETWORKS or row["asset"] not in {"TRX", "TRC20"}:
        raise ValueError("F41_NETWORK_ASSET_INVALID")
    if not tron_address(row["recipient"]):
        raise ValueError("F41_RECIPIENT_CHECKSUM_INVALID")
    if row["asset"] == "TRC20":
        if not tron_address(row["token_contract"]):
            raise ValueError("F41_TOKEN_CHECKSUM_INVALID")
    elif row["token_contract"]:
        raise ValueError("F41_TRX_HAS_TOKEN_CONTRACT")
    if not AMOUNT.fullmatch(row["amount_base_units"]):
        raise ValueError("F41_AMOUNT_INVALID")
    if payment and not HEX64.fullmatch(row["txid"]):
        raise ValueError("F41_TXID_INVALID")


def row_csv(rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in fields})
    return stream.getvalue().encode("utf-8")


def render(invoice_blob, payment_blob):
    invoices = read_csv(invoice_blob, INV_FIELDS, 5000)
    payments = read_csv(payment_blob, PAY_FIELDS, 20000)
    if not invoices:
        raise ValueError("F41_NO_INVOICES")
    invoice_map = {}
    for row in invoices:
        validate_record(row, False)
        if row["invoice_id"] in invoice_map:
            raise ValueError("F41_DUPLICATE_INVOICE")
        invoice_map[row["invoice_id"]] = row
    payment_map = defaultdict(list)
    tx_counts = Counter()
    for row in payments:
        validate_record(row, True)
        txid = row["txid"].lower()
        tx_counts[txid] += 1
        payment_map[row["invoice_id"]].append(row)
    report = []
    statuses = Counter()
    for ident, inv in sorted(invoice_map.items()):
        related = payment_map[ident]
        amount = sum(int(item["amount_base_units"]) for item in related)
        if not related:
            status = "NO_PAYMENT_IN_EXPORT"
            action = "Locate payment data or request payer evidence"
        elif any(tx_counts[p["txid"].lower()] > 1 for p in related):
            status = "DUPLICATE_TXID_REVIEW"
            action = "Investigate payment references reused across rows"
        elif any(any(p[k] != inv[k] for k in ("network", "asset", "recipient", "token_contract")) for p in related):
            status = "FIELDS_MISMATCH_REVIEW"
            action = "Inspect network, asset, recipient and token contract"
        elif len(related) > 1:
            status = "MULTIPLE_PAYMENTS_REVIEW"
            action = "Review multi-payment allocation and finality externally"
        elif amount < int(inv["amount_base_units"]):
            status = "UNDERPAID_IN_EXPORT"
            action = "Resolve amount difference and check source independently"
        elif amount > int(inv["amount_base_units"]):
            status = "OVERPAID_IN_EXPORT"
            action = "Resolve overpayment and check source independently"
        else:
            status = "MATCHED_EXPORT_UNVERIFIED"
            action = "Verify on-chain finality independently before any delivery"
        statuses[status] += 1
        report.append({
            "invoice_id": ident, "network": inv["network"], "asset": inv["asset"],
            "expected_base_units": inv["amount_base_units"],
            "exported_base_units": str(amount),
            "payment_rows": len(related), "status": status,
            "recommended_action": action, "chain_finality_verified": False,
            "delivery_authorized": False
        })
    orphans = [
        {"invoice_id": ident, "rows": len(rows),
         "txids": sorted(set(r["txid"].lower() for r in rows))}
        for ident, rows in sorted(payment_map.items()) if ident not in invoice_map
    ]
    report_data = {
        "schema": SCHEMA, "chain_finality_verified": False,
        "settlement_authorized": False, "delivery_authorized": False,
        "payments_broadcast": 0, "site_writes": 0,
        "invoices": report, "orphaned_payments": orphans,
        "summary": {"invoice_count": len(invoices), "payment_row_count": len(payments),
                    "unlinked_invoice_ids": len(orphans), "status_counts": dict(sorted(statuses.items()))}
    }
    cols = ["invoice_id", "network", "asset", "expected_base_units",
            "exported_base_units", "payment_rows", "status", "recommended_action",
            "chain_finality_verified", "delivery_authorized"]
    report_csv = row_csv(
        [dict(r, chain_finality_verified="false", delivery_authorized="false") for r in report], cols)
    orphan_cols = ["invoice_id", "payment_rows", "txids"]
    orphan_csv = row_csv(
        [{"invoice_id": r["invoice_id"], "payment_rows": r["rows"],
          "txids": ";".join(r["txids"])} for r in orphans], orphan_cols)
    return {
        "report.json": encoded(report_data),
        "invoice_review.csv": report_csv,
        "unlinked_payments.csv": orphan_csv
    }


def expected_manifest(invoice_blob, payment_blob, output):
    return {
        "schema": SCHEMA + ".integrity.v1", "offline_candidate_only": True,
        "input_sha256": {"invoices.csv": digest(invoice_blob),
                         "payments.csv": digest(payment_blob)},
        "output_sha256": {name: digest(blob) for name, blob in sorted(output.items())},
        "seller_or_customer_signature": None,
        "independent_chain_proof": False, "independent_commercial_review": False,
        "public_listing_approved": False, "real_sales_proven": False
    }


def build(invoice_path, payment_path, out, verify_only=False):
    invoice_blob = input_bytes(invoice_path)
    payment_blob = input_bytes(payment_path)
    output = render(invoice_blob, payment_blob)
    manifest = encoded(expected_manifest(invoice_blob, payment_blob, output))
    expected = dict(output, **{"integrity.json": manifest})
    dst = Path(out)
    if verify_only:
        if not dst.is_dir() or dst.is_symlink():
            raise ValueError("F41_OUTPUT_NOT_DIRECTORY")
        found = set()
        for item in dst.rglob("*"):
            if item.is_symlink():
                raise ValueError("F41_OUTPUT_SYMLINK")
            if item.is_file():
                found.add(item.relative_to(dst).as_posix())
        if found != set(expected):
            raise ValueError("F41_OUTPUT_MEMBERS_CHANGED")
        for name, blob in expected.items():
            if (dst / name).read_bytes() != blob:
                raise ValueError("F41_OUTPUT_INTEGRITY_FAILED:" + name)
        return expected_manifest(invoice_blob, payment_blob, output)
    if dst.exists() or dst.is_symlink() or not dst.parent.is_dir() or dst.parent.is_symlink():
        raise ValueError("F41_OUTPUT_MUST_BE_NEW")
    stage = Path(tempfile.mkdtemp(prefix=".f41-merchant-", dir=str(dst.parent)))
    try:
        os.chmod(stage, 0o700)
        for name, blob in expected.items():
            path = stage / name
            with path.open("xb") as stream:
                stream.write(blob)
            os.chmod(path, 0o600)
        os.rename(stage, dst)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return expected_manifest(invoice_blob, payment_blob, output)


def main():
    parser = argparse.ArgumentParser(description="Private/offline F41 merchant export audit; never verifies blockchain payment")
    parser.add_argument("--invoices", required=True)
    parser.add_argument("--payments", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    details = build(args.invoices, args.payments, args.out, args.verify)
    print("F41_MERCHANT_AUDIT_INTEGRITY=PASS")
    print("F41_INPUT_INVOICE_SHA256=" + details["input_sha256"]["invoices.csv"])
    print("F41_CHAIN_FINALITY_CERTIFIED=false")
    print("F41_DELIVERY_AUTHORIZED=false")


if __name__ == "__main__":
    main()
