#!/usr/bin/env python3
"""F41 Shasta-only, read-only TRX finality check for private reconciliation candidates.

It does not sign, broadcast, settle, deliver, trade, or accept caller-selected RPCs.
The original immutable F41 artifact and master AgentTasks remain unchanged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.error
import urllib.request
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import factory_f41_multi_product_builder as builder

SCHEMA = "saeit.factory.f41-shasta-finality.v1"
NODE = "https://api.shasta.trongrid.io/walletsolidity/gettransactionbyid"
NODE_INFO = "https://api.shasta.trongrid.io/walletsolidity/gettransactioninfobyid"
TRANSFER_TOPIC = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TOPIC = re.compile(r"[0-9a-fA-F]{64}\Z")
TX = re.compile(r"[a-fA-F0-9]{64}\Z")
ADDRESS = re.compile(r"41[a-fA-F0-9]{40}\Z")
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf8")


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def tron_hex(address):
    if type(address) is not str or len(address) != 34 or not address.startswith("T"):
        raise ValueError("F41_TRON_ADDRESS_FORMAT")
    number = 0
    for ch in address:
        if ch not in B58:
            raise ValueError("F41_TRON_BASE58_INVALID")
        number = number * 58 + B58.index(ch)
    body = number.to_bytes((number.bit_length() + 7) // 8, "big")
    body = b"\x00" * (len(address) - len(address.lstrip("1"))) + body
    if len(body) != 25 or body[:1] != b"\x41":
        raise ValueError("F41_TRON_ADDRESS_LENGTH")
    expected = hashlib.sha256(hashlib.sha256(body[:21]).digest()).digest()[:4]
    if body[21:] != expected:
        raise ValueError("F41_TRON_ADDRESS_CHECKSUM")
    return body[:21].hex()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _solidity_query(txid, endpoint):
    """Only two pinned read-only Shasta SolidityNode RPCs are permitted."""
    if endpoint not in (NODE, NODE_INFO):
        raise ValueError("F41_RPC_ENDPOINT_NOT_ALLOWLISTED")
    if type(txid) is not str or not TX.fullmatch(txid):
        raise ValueError("F41_TXID_INVALID")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    key = os.environ.get("F41_TRON_PRO_API_KEY", "")
    if key:
        if len(key) > 256 or not key.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in key):
            raise ValueError("F41_RPC_KEY_INVALID")
        headers["TRON-PRO-API-KEY"] = key
    request = urllib.request.Request(
        endpoint, data=canonical({"value": txid.lower()}).strip(),
        headers=headers, method="POST")
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=10) as response:
        if response.status != 200:
            raise ValueError("F41_RPC_HTTP_FAILURE")
        if response.headers.get_content_type() != "application/json":
            raise ValueError("F41_RPC_CONTENT_TYPE")
        payload = response.read(131073)
    if len(payload) > 131072:
        raise ValueError("F41_RPC_RESPONSE_TOO_LARGE")
    result = json.loads(payload)
    if type(result) is not dict:
        raise ValueError("F41_RPC_RESPONSE_NOT_OBJECT")
    return result


def solidity_lookup(txid):
    return _solidity_query(txid, NODE)


def solidity_receipt_lookup(txid):
    return _solidity_query(txid, NODE_INFO)


def approved_token_contracts():
    """Explicit Shasta-only operator approval, never derived from buyer input."""
    raw = os.environ.get("F41_SHASTA_TRC20_ALLOWLIST", "")
    if len(raw) > 512:
        raise ValueError("F41_TRC20_ALLOWLIST_TOO_LARGE")
    if not raw:
        return set()
    parts = raw.split(",")
    if len(parts) > 8 or any(not p or p.strip() != p for p in parts):
        raise ValueError("F41_TRC20_ALLOWLIST_INVALID")
    decoded = {tron_hex(p) for p in parts}
    if len(decoded) != len(parts):
        raise ValueError("F41_TRC20_ALLOWLIST_DUPLICATES")
    return decoded


def check_trc20_body(obs, transaction):
    if type(transaction) is not dict:
        return "TRC20_BODY_INVALID"
    if not transaction:
        return "NOT_YET_VISIBLE_ON_SOLIDITY_NODE"
    txid = transaction.get("txID")
    if type(txid) is not str or not TX.fullmatch(txid) or txid.lower() != obs["txid"].lower():
        return "TRC20_BODY_TXID_MISMATCH"
    if transaction.get("visible") is True:
        return "TRC20_BODY_VISIBLE_FORMAT_UNEXPECTED"
    contracts = transaction.get("raw_data", {}).get("contract") if type(transaction.get("raw_data")) is dict else None
    ret = transaction.get("ret")
    if (type(contracts) is not list or len(contracts) != 1 or
            type(contracts[0]) is not dict or contracts[0].get("type") != "TriggerSmartContract" or
            type(ret) is not list or len(ret) != 1 or type(ret[0]) is not dict or
            ret[0].get("contractRet") != "SUCCESS"):
        return "TRC20_BODY_EXECUTION_OR_CONTRACT_INVALID"
    return None


def check_trc20_receipt(inv, obs, receipt, contract_hex):
    """Require one exact Transfer log from an approved TRC20 contract, solidified."""
    if type(receipt) is not dict or not receipt:
        return "TRC20_FINAL_RECEIPT_NOT_AVAILABLE", False
    txid = receipt.get("id")
    if (type(txid) is not str or not TX.fullmatch(txid) or
            txid.lower() != obs["txid"].lower()):
        return "TRC20_RECEIPT_TXID_MISMATCH", False
    if (receipt.get("result") == "FAILED" or
            type(receipt.get("blockNumber")) is not int or receipt["blockNumber"] <= 0 or
            type(receipt.get("receipt")) is not dict or
            receipt["receipt"].get("result") != "SUCCESS"):
        return "TRC20_RECEIPT_NOT_SUCCESSFUL", False
    logs = receipt.get("log", [])
    if type(logs) is not list or len(logs) > 256:
        return "TRC20_LOG_INVENTORY_INVALID", False
    recipient_hex = tron_hex(inv["recipient"])[2:]
    contract_id = contract_hex[2:]
    expected = builder.positive(inv["amount_base_units"])
    matches = 0
    for log in logs:
        if type(log) is not dict:
            return "TRC20_LOG_MALFORMED", False
        address, topics, data = log.get("address"), log.get("topics"), log.get("data")
        if type(address) is not str or not re.fullmatch(r"[0-9a-fA-F]{40}", address):
            return "TRC20_LOG_ADDRESS_INVALID", False
        if address.lower() != contract_id:
            continue
        if (type(topics) is not list or len(topics) != 3 or
                any(type(t) is not str or not TOPIC.fullmatch(t) for t in topics)):
            return "TRC20_APPROVED_CONTRACT_EVENT_INVALID", False
        if topics[0].lower() != TRANSFER_TOPIC:
            continue
        if (not topics[1].startswith("0" * 24) or
                not topics[2].startswith("0" * 24) or
                type(data) is not str or not TOPIC.fullmatch(data)):
            return "TRC20_TRANSFER_ENCODING_INVALID", False
        if (int(topics[1][24:], 16) == 0 or
                topics[2][24:].lower() != recipient_hex or
                int(data, 16) != expected):
            continue
        matches += 1
    if matches == 1:
        return "FINALIZED_ALLOWLISTED_TRC20_TRANSFER_ON_SHASTA", True
    if matches > 1:
        return "TRC20_DUPLICATE_MATCHING_EVENTS", False
    return "TRC20_APPROVED_TRANSFER_NOT_MATCHED", False


def check_chain(inv, obs, transaction):
    """Return (status, finalized); malformed node data must never confirm payment."""
    if type(transaction) is not dict:
        return "RPC_RESPONSE_UNTRUSTED", False
    if not transaction:
        return "NOT_YET_VISIBLE_ON_SOLIDITY_NODE", False
    txid = transaction.get("txID")
    if type(txid) is not str or not TX.fullmatch(txid) or txid.lower() != obs["txid"].lower():
        return "CHAIN_TXID_INTEGRITY_FAILURE", False
    raw = transaction.get("raw_data")
    ret = transaction.get("ret")
    if type(raw) is not dict or type(ret) is not list or len(ret) != 1 or type(ret[0]) is not dict:
        return "CHAIN_EXECUTION_PROOF_MISSING", False
    if ret[0].get("contractRet") != "SUCCESS":
        return "CHAIN_EXECUTION_UNSUCCESSFUL", False
    contracts = raw.get("contract")
    if type(contracts) is not list or len(contracts) != 1 or type(contracts[0]) is not dict:
        return "CHAIN_CONTRACT_UNTRUSTED", False
    contract = contracts[0]
    if contract.get("type") != "TransferContract":
        return "CHAIN_NOT_A_NATIVE_TRX_TRANSFER", False
    parameter = contract.get("parameter")
    if type(parameter) is not dict or type(parameter.get("value")) is not dict:
        return "CHAIN_TRANSFER_FIELDS_MISSING", False
    details = parameter["value"]
    amount = details.get("amount")
    address = details.get("to_address")
    if (type(amount) is not int or amount < 1 or type(address) is not str
            or not ADDRESS.fullmatch(address)):
        return "CHAIN_TRANSFER_FIELDS_INVALID", False
    try:
        wanted = tron_hex(inv["recipient"])
    except ValueError:
        return "INVOICE_ADDRESS_INVALID", False
    if address.lower() != wanted or amount != builder.positive(inv["amount_base_units"]):
        return "CHAIN_AMOUNT_OR_RECIPIENT_MISMATCH", False
    if transaction.get("visible") is True:
        return "CHAIN_VISIBLE_FORMAT_UNEXPECTED", False
    return "FINALIZED_TRX_MATCH_ON_SHASTA", True


def evaluate(spec, lookup=solidity_lookup, receipt_lookup=solidity_receipt_lookup):
    if (type(spec) is not dict or spec.get("kind") != "reconciliation"
            or spec.get("schema") != builder.SCHEMA
            or type(spec.get("data")) is not dict):
        raise ValueError("F41_FINALITY_REQUIRES_RECONCILIATION_SPEC")
    # Existing bounded validator checks invoice IDs, duplicate txids, decimal units, and bounds.
    builder.reconciliation(spec["data"])
    invoices = {x["id"]: x for x in spec["data"]["invoices"]}
    observations = {ident: [] for ident in invoices}
    txids = set()
    for row in spec["data"]["observations"]:
        txid = row["txid"].lower()
        if txid in txids:
            raise ValueError("F41_DUPLICATE_CASEFOLDED_TXID")
        txids.add(txid)
        observations[row["invoice_id"]].append(row)
    records = []
    for ident in sorted(invoices):
        inv = invoices[ident]
        hits = observations[ident]
        status, final = "NO_OBSERVATION", False
        txid = None
        if len(hits) > 1:
            status = "MULTIPLE_TRANSACTIONS_MANUAL_REVIEW"
        elif len(hits) == 1:
            obs = hits[0]
            txid = obs["txid"].lower()
            if any(obs[field] != inv[field] for field in ("network", "asset", "recipient", "amount_base_units")):
                status = "OBSERVATION_INVOICE_MISMATCH"
            elif inv["asset"] == "TRC20":
                try:
                    token = tron_hex(inv["token_contract"])
                    allowlist = approved_token_contracts()
                    if token not in allowlist:
                        status = "TRC20_CONTRACT_NOT_APPROVED"
                    else:
                        body = lookup(txid)
                        body_error = check_trc20_body(obs, body)
                        if body_error is not None:
                            status = body_error
                        else:
                            status, final = check_trc20_receipt(
                                inv, obs, receipt_lookup(txid), token)
                except (OSError, TimeoutError, ValueError, json.JSONDecodeError,
                        urllib.error.URLError, UnicodeError, OverflowError):
                    status = "TRC20_NODE_OR_CONTRACT_CONFIG_INVALID"
            else:
                try:
                    response = lookup(txid)
                    status, final = check_chain(inv, obs, response)
                except (OSError, TimeoutError, ValueError, json.JSONDecodeError,
                        urllib.error.URLError, UnicodeError, OverflowError):
                    status = "SOLIDITY_NODE_UNAVAILABLE_OR_INVALID"
        records.append({
            "invoice_id": ident, "txid": txid, "status": status,
            "solidity_finality_verified": final,
            "delivery_authorized": False,
        })
    return {
        "schema": SCHEMA, "network": "shasta", "asset_scope": "native_TRX_and_allowlisted_TRC20",
        "solidity_endpoint": NODE,
        "original_request_sha256": checksum(builder.enc(spec)),
        "records": records,
        "verified_match_count": sum(int(x["solidity_finality_verified"]) for x in records),
        "all_invoices_finalized": bool(records) and all(x["solidity_finality_verified"] for x in records),
        "simulation_used": lookup is not solidity_lookup or receipt_lookup is not solidity_receipt_lookup,
        "customer_delivery_enabled": False, "mainnet_enabled": False,
        "financial_actions": 0, "transaction_broadcasts": 0,
        "quality_1000_certified": False, "market_liquidity_proven": False,
    }


def write_private(spec_path, out_path):
    spec = builder.read_request(spec_path)
    if spec["kind"] != "reconciliation":
        raise ValueError("F41_FINALITY_WRONG_KIND")
    dst = Path(out_path)
    parent = dst.parent
    if (dst.exists() or dst.is_symlink() or not parent.is_dir()
            or parent.is_symlink() or dst.name in ("", ".", "..")):
        raise ValueError("F41_FINALITY_OUTPUT_MUST_BE_NEW")
    report = evaluate(spec)
    if report["simulation_used"]:
        raise ValueError("F41_FINALITY_SIMULATION_CANNOT_BE_INSTALLED")
    # New private folder only, never overwrite old evidence or deliver to customer.
    with tempfile.TemporaryDirectory(prefix=".f41-solidity-", dir=str(parent)) as temp:
        tempdir = Path(temp)
        os.chmod(tempdir, 0o700)
        body = canonical(report)
        result = tempdir / "finality.json"
        with result.open("xb") as stream:
            stream.write(body)
        os.chmod(result, 0o600)
        manifest = {
            "schema": "saeit.factory.f41-finality-evidence.v1",
            "finality_sha256": checksum(body),
            "spec_sha256": checksum(builder.enc(spec)),
            "live_solidity_queries_only": True,
            "customer_delivery_enabled": False, "signed_attestation": False,
        }
        meta = tempdir / "manifest.json"
        with meta.open("xb") as stream:
            stream.write(canonical(manifest))
        os.chmod(meta, 0o600)
        os.rename(tempdir, dst)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = write_private(args.spec, args.out)
    print("F41_SHASTA_FINALITY_READ_ONLY=PASS")
    print("F41_FINALIZED_TRX_MATCH_COUNT=%d" % report["verified_match_count"])
    print("F41_INVOICE_COUNT=%d" % len(report["records"]))
    print("F41_CUSTOMER_DELIVERY_ENABLED=false")
    print("F41_FINANCIAL_ACTIONS=0")


if __name__ == "__main__":
    main()
