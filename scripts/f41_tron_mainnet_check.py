#!/usr/bin/env python3
"""F41 private, read-only TRON mainnet solidity evidence for merchant CSV invoices.

This neither signs nor broadcasts anything. It never authorizes settlement or delivery.
The only external data source is a pinned TRON mainnet SolidityNode endpoint.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import urllib.error
import urllib.request

import f41_merchant_audit_cli as audit

SCHEMA = "saeit.f41.merchant-tron-mainnet-evidence.v1"
BODY_URL = "https://api.trongrid.io/walletsolidity/gettransactionbyid"
INFO_URL = "https://api.trongrid.io/walletsolidity/gettransactioninfobyid"
TOPIC_TRANSFER = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
HEXLONG = re.compile(r"[A-Fa-f0-9]{64}\Z")
HEX40 = re.compile(r"[A-Fa-f0-9]{40}\Z")
HEX42 = re.compile(r"41[A-Fa-f0-9]{40}\Z")
MAX_CANDIDATES = 10


def clean_json(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf8")


def checksum(obj):
    return hashlib.sha256(clean_json(obj)).hexdigest()


def tron_hex(address):
    if not audit.tron_address(address):
        raise ValueError("F41_TRON_ADDRESS_CHECKSUM")
    n = 0
    for char in address:
        n = 58 * n + audit.B58.index(char)
    return n.to_bytes(25, "big")[:21].hex()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def rpc(txid, url):
    if url not in (BODY_URL, INFO_URL):
        raise ValueError("F41_RPC_ENDPOINT_NOT_APPROVED")
    if type(txid) is not str or not HEXLONG.fullmatch(txid):
        raise ValueError("F41_TXID_INVALID")
    key = os.environ.get("F41_MAINNET_TRON_PRO_API_KEY", "")
    if key and (len(key) > 256 or not key.isascii()
                or any(ord(c) < 33 or ord(c) > 126 for c in key)):
        raise ValueError("F41_RPC_KEY_INVALID")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if key:
        headers["TRON-PRO-API-KEY"] = key
    request = urllib.request.Request(url, data=clean_json({"value": txid.lower()}).strip(),
                                     headers=headers, method="POST")
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as result:
        if result.status != 200 or result.headers.get_content_type() != "application/json":
            raise ValueError("F41_RPC_HTTP_OR_TYPE_ERROR")
        raw = result.read(131073)
    if len(raw) > 131072:
        raise ValueError("F41_RPC_TOO_LARGE")
    parsed = json.loads(raw)
    if type(parsed) is not dict or "Error" in parsed:
        raise ValueError("F41_RPC_ERROR_RESPONSE")
    return parsed


def body(txid):
    return rpc(txid, BODY_URL)


def info(txid):
    return rpc(txid, INFO_URL)


def approved_tokens():
    """Admin-supplied approved contract list. Merchant CSV cannot approve tokens."""
    raw = os.environ.get("F41_MAINNET_TRC20_ALLOWLIST", "")
    if len(raw) > 512:
        raise ValueError("F41_TRC20_ALLOWLIST_LENGTH")
    if not raw:
        return set()
    addresses = raw.split(",")
    if len(addresses) > 8 or any(x.strip() != x or not x for x in addresses):
        raise ValueError("F41_TRC20_ALLOWLIST_FORMAT")
    selected = {tron_hex(x) for x in addresses}
    if len(selected) != len(addresses):
        raise ValueError("F41_TRC20_ALLOWLIST_DUPLICATE")
    return selected


def success_body(transaction, txid, kind):
    if type(transaction) is not dict or not transaction:
        return "SOLIDITY_BODY_NOT_FOUND"
    if (type(transaction.get("txID")) is not str or
            transaction["txID"].lower() != txid or
            not HEXLONG.fullmatch(transaction["txID"])):
        return "BODY_TXID_MISMATCH"
    ret = transaction.get("ret")
    contracts = transaction.get("raw_data", {}).get("contract") if type(transaction.get("raw_data")) is dict else None
    if (transaction.get("visible") is True or type(ret) is not list or len(ret) != 1 or
            type(ret[0]) is not dict or ret[0].get("contractRet") != "SUCCESS" or
            type(contracts) is not list or len(contracts) != 1 or
            type(contracts[0]) is not dict or contracts[0].get("type") != kind):
        return "BODY_EXECUTION_OR_CONTRACT_INVALID"
    return None


def check_trx(inv, txid, transaction):
    error = success_body(transaction, txid, "TransferContract")
    if error:
        return error, False
    value = transaction["raw_data"]["contract"][0].get("parameter", {}).get("value")
    if type(value) is not dict:
        return "TRX_TRANSFER_FIELDS_MISSING", False
    amount, recipient = value.get("amount"), value.get("to_address")
    if type(amount) is not int or type(recipient) is not str or not HEX42.fullmatch(recipient):
        return "TRX_TRANSFER_FIELDS_INVALID", False
    if amount != int(inv["amount_base_units"]) or recipient.lower() != tron_hex(inv["recipient"]):
        return "TRX_AMOUNT_OR_RECIPIENT_MISMATCH", False
    # SolidityNode body is only returned after solidification.
    return "TRX_SOLIDIFIED_NODE_MATCH", True


def check_token(inv, txid, transaction, receipt, token_hex):
    error = success_body(transaction, txid, "TriggerSmartContract")
    if error:
        return error, False
    if type(receipt) is not dict or not receipt:
        return "TRC20_SOLIDITY_RECEIPT_NOT_FOUND", False
    if (type(receipt.get("id")) is not str or
            not HEXLONG.fullmatch(receipt["id"]) or receipt["id"].lower() != txid):
        return "TRC20_RECEIPT_TXID_MISMATCH", False
    inner = receipt.get("receipt")
    if (type(receipt.get("blockNumber")) is not int or receipt["blockNumber"] <= 0 or
            type(inner) is not dict or inner.get("result") != "SUCCESS" or
            receipt.get("result") == "FAILED"):
        return "TRC20_EXECUTION_NOT_FINAL_SUCCESS", False
    logs = receipt.get("log", [])
    if type(logs) is not list or len(logs) > 256:
        return "TRC20_RECEIPT_LOGS_INVALID", False
    token = token_hex[2:]
    recipient = tron_hex(inv["recipient"])[2:]
    amount = int(inv["amount_base_units"])
    matches = 0
    for event in logs:
        if type(event) is not dict:
            return "TRC20_EVENT_MALFORMED", False
        contract_id = event.get("address")
        if type(contract_id) is not str or not HEX40.fullmatch(contract_id):
            return "TRC20_EVENT_CONTRACT_MALFORMED", False
        if contract_id.lower() != token:
            continue
        topics = event.get("topics")
        data = event.get("data")
        if (type(topics) is not list or len(topics) != 3 or
                any(type(t) is not str or not HEXLONG.fullmatch(t) for t in topics)):
            return "TRC20_APPROVED_EVENT_MALFORMED", False
        if topics[0].lower() != TOPIC_TRANSFER:
            continue
        if (not topics[1].lower().startswith("0" * 24) or
                not topics[2].lower().startswith("0" * 24) or
                type(data) is not str or not HEXLONG.fullmatch(data)):
            return "TRC20_ABI_TRANSFER_MALFORMED", False
        if (int(topics[1][24:], 16) > 0 and topics[2][24:].lower() == recipient
                and int(data, 16) == amount):
            matches += 1
    if matches != 1:
        return ("TRC20_AMBIGUOUS_MATCHING_EVENTS" if matches > 1 else
                "TRC20_APPROVED_TRANSFER_NOT_MATCHED"), False
    return "TRC20_SOLIDIFIED_NODE_MATCH", True


def evaluate(invoice_blob, payment_blob, lookup=body, receipt_lookup=info, tokens=None):
    baseline = json.loads(audit.render(invoice_blob, payment_blob)["report.json"])
    invoices = audit.read_csv(invoice_blob, audit.INV_FIELDS, 5000)
    payments = audit.read_csv(payment_blob, audit.PAY_FIELDS, 20000)
    inv_map = {row["invoice_id"]: row for row in invoices}
    pay_map = {row["invoice_id"]: row for row in payments}
    candidates = [row for row in baseline["invoices"]
                  if row["network"] == "tron-mainnet" and
                  row["status"] == "MATCHED_EXPORT_UNVERIFIED"]
    if len(candidates) > MAX_CANDIDATES:
        raise ValueError("F41_MAINNET_QUERY_BUDGET_EXCEEDED")
    if tokens is None:
        tokens = approved_tokens()
    if type(tokens) is not set or any(type(x) is not str or not HEX42.fullmatch(x) for x in tokens):
        raise ValueError("F41_APPROVED_TOKEN_CONFIG_INVALID")
    simulated = lookup is not body or receipt_lookup is not info
    entries = []
    calls = 0
    for record in baseline["invoices"]:
        ident = record["invoice_id"]
        inv = inv_map[ident]
        status = "NOT_ELIGIBLE_UNVERIFIED_EXPORT"
        matches = False
        body_digest = None
        receipt_digest = None
        txid = None
        if record in candidates:
            obs = pay_map[ident]
            txid = obs["txid"].lower()
            try:
                if inv["asset"] == "TRC20" and tron_hex(inv["token_contract"]) not in tokens:
                    status = "TOKEN_CONTRACT_NOT_OPERATOR_APPROVED"
                else:
                    calls += 1
                    transaction = lookup(txid)
                    body_digest = checksum(transaction)
                    if inv["asset"] == "TRX":
                        status, matches = check_trx(inv, txid, transaction)
                    else:
                        if success_body(transaction, txid, "TriggerSmartContract") is None:
                            calls += 1
                            receipt = receipt_lookup(txid)
                        else:
                            receipt = {}
                        receipt_digest = checksum(receipt) if receipt else None
                        status, matches = check_token(inv, txid, transaction, receipt, tron_hex(inv["token_contract"]))
            except (ValueError, OSError, TimeoutError, UnicodeError,
                    urllib.error.URLError, json.JSONDecodeError, OverflowError):
                status, matches = "MAINNET_NODE_UNAVAILABLE_OR_INVALID", False
        if matches and simulated:
            status = "SIMULATED_MATCH_NOT_LIVE_EVIDENCE"
        entries.append({
            "invoice_id": ident, "txid": txid, "status": status,
            "node_payload_matches_invoice": matches,
            "live_solidified_node_evidence": bool(matches and not simulated),
            "body_response_sha256": body_digest,
            "receipt_response_sha256": receipt_digest,
            "delivery_authorized": False,
        })
    return {
        "schema": SCHEMA, "network": "tron-mainnet",
        "body_endpoint": BODY_URL, "receipt_endpoint": INFO_URL,
        "input_sha256": {"invoices.csv": hashlib.sha256(invoice_blob).hexdigest(),
                         "payments.csv": hashlib.sha256(payment_blob).hexdigest()},
        "records": entries, "query_candidates": len(candidates),
        "network_lookups_attempted": calls,
        "live_matched_count": sum(int(x["live_solidified_node_evidence"]) for x in entries),
        "simulation": simulated, "proofs_are_node_responses_not_independent_audits": True,
        "signed_by_owner": False, "customer_delivery_authorized": False,
        "payments_broadcast": 0, "site_writes": 0, "revenue_proven": False
    }


def write_private(invoices, payments, out):
    inv, pay = audit.input_bytes(invoices), audit.input_bytes(payments)
    report = evaluate(inv, pay)
    if report["simulation"]:
        raise ValueError("F41_SIMULATION_MUST_NOT_BE_PUBLISHED_AS_EVIDENCE")
    dst = Path(out)
    if dst.is_symlink() or dst.exists() or not dst.parent.is_dir() or dst.parent.is_symlink():
        raise ValueError("F41_OUTPUT_MUST_BE_NEW")
    with tempfile.TemporaryDirectory(prefix=".f41-mainnet-", dir=str(dst.parent)) as folder:
        root = Path(folder)
        os.chmod(root, 0o700)
        blob = clean_json(report)
        data = root / "node-evidence.json"
        data.write_bytes(blob)
        os.chmod(data, 0o600)
        manifest = root / "integrity.json"
        manifest.write_bytes(clean_json({
            "schema": SCHEMA + ".integrity.v1",
            "node_evidence_sha256": hashlib.sha256(blob).hexdigest(),
            "input_sha256": report["input_sha256"],
            "live_rpc_requests_only": True,
            "owner_signature": None,
            "manual_review_required": True,
            "public_listing_approved": False
        }))
        os.chmod(manifest, 0o600)
        os.rename(root, dst)
    return report


def main():
    parser = argparse.ArgumentParser(description="Read-only TRON mainnet verification; never authorizes buyer delivery")
    parser.add_argument("--invoices", required=True)
    parser.add_argument("--payments", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = write_private(args.invoices, args.payments, args.out)
    print("F41_MAINNET_READONLY_LOOKUPS=" + str(report["network_lookups_attempted"]))
    print("F41_MAINNET_SOLIDIFIED_NODE_MATCHES=" + str(report["live_matched_count"]))
    print("F41_MAINNET_CUSTOMER_DELIVERY_AUTHORIZED=false")
    print("F41_MAINNET_FINANCIAL_ACTIONS=0")


if __name__ == "__main__":
    main()
