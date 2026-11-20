"""MOJ-PROP-01 native TRX evidence validator. Offline; never authorizes checkout.

Only independently authenticated SolidityNode responses are eligible input.
Caller MUST enforce legal, contract, KYC, funding, broker, receiver ownership,
network identity, immutable enrollment/order, and atomic database uniqueness.
This module deliberately creates no invoice, receipt, enrollment, or credit.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import re

SKU = "MOJ-PROP-01"
NETWORK = "TRON-mainnet"
AMOUNT_SUN = 30_000_000
TXID = re.compile(r"[0-9a-f]{64}\\Z")
HEX = re.compile(r"(?:[0-9a-f]{2})+\\Z")
TRON_HEX = re.compile(r"41[0-9a-f]{40}\\Z")
TRANSFER_CONTRACT = "TransferContract"


class ProofRejected(ValueError):
    """An evidence field is missing, untrusted, malformed or inconsistent."""


@dataclass(frozen=True)
class NativeTransferEvidence:
    network: str
    txid: str
    order_ref: str
    enrollment_ref: str
    recipient_hex: str
    amount_sun: int
    solidity_block_number: int
    solidity_block_id: str
    evidence_sha256: str
    state: str = "SOLIDIFIED_EVIDENCE_ONLY"
    payable: bool = False
    credited: bool = False
    receipt_issued: bool = False
    enrollment_activated: bool = False


def verify_native_plan1_transfer(*, order: dict, owner_receiver_hex: str,
                                  transaction: dict, transaction_info: dict,
                                  attestation: dict) -> NativeTransferEvidence:
    """Check a strict independent *evidence snapshot*, not a payment authorization.

    attestation must originate from a trusted, independently authenticated
    SolidityNode adapter, not a customer or a public browser request. The
    adapter must validate endpoint TLS, chain genesis and node provenance.
    Atomic UNIQUE(network,txid) and order state are separate DB obligations.
    """
    if type(order) is not dict or set(order) != {
        "sku", "network", "amount_sun", "order_ref", "enrollment_ref",
        "terms_version", "recipient_hex", "txid",
    }:
        raise ProofRejected("exact immutable Plan 1 order snapshot required")
    if order["sku"] != SKU or order["network"] != NETWORK:
        raise ProofRejected("wrong product or chain")
    if type(order["amount_sun"]) is not int or order["amount_sun"] != AMOUNT_SUN:
        raise ProofRejected("exact native SUN amount required")
    if any(type(order[k]) is not str or not 1 <= len(order[k]) <= 128
           for k in ("order_ref", "enrollment_ref", "terms_version")):
        raise ProofRejected("versioned order/enrollment identity missing")
    if (type(owner_receiver_hex) is not str or
        TRON_HEX.fullmatch(owner_receiver_hex) is None or
        order["recipient_hex"] != owner_receiver_hex):
        raise ProofRejected("independently verified owner recipient required")
    txid = order["txid"]
    if type(txid) is not str or TXID.fullmatch(txid) is None:
        raise ProofRejected("canonical transaction id required")
    if type(transaction) is not dict or transaction.get("txID") != txid:
        raise ProofRejected("solidity transaction absent or wrong id")
    raw = transaction.get("raw_data")
    if type(raw) is not dict:
        raise ProofRejected("missing raw transaction")
    contracts = raw.get("contract")
    if type(contracts) is not list or len(contracts) != 1:
        raise ProofRejected("exactly one native transfer required")
    contract = contracts[0]
    if type(contract) is not dict or contract.get("type") != TRANSFER_CONTRACT:
        raise ProofRejected("not a native TRX transfer")
    parameter = contract.get("parameter")
    if type(parameter) is not dict or type(parameter.get("value")) is not dict:
        raise ProofRejected("native transfer parameters missing")
    value = parameter["value"]
    if type(value.get("amount")) is not int or value["amount"] != AMOUNT_SUN:
        raise ProofRejected("transfer amount mismatch")
    if value.get("to_address") != owner_receiver_hex:
        raise ProofRejected("transfer destination mismatch")
    sender = value.get("owner_address")
    if type(sender) is not str or TRON_HEX.fullmatch(sender) is None:
        raise ProofRejected("malformed sender")
    if sender == owner_receiver_hex:
        raise ProofRejected("self transfer cannot qualify as purchase")
    if type(transaction_info) is not dict or transaction_info.get("id") != txid:
        raise ProofRejected("independent solidity receipt missing")
    if transaction_info.get("receipt", {}).get("result") != "SUCCESS":
        raise ProofRejected("receipt not successful")
    if type(transaction_info.get("blockNumber")) is not int or transaction_info["blockNumber"] <= 0:
        raise ProofRejected("confirmed block number missing")
    if transaction_info.get("fee") is None or type(transaction_info["fee"]) is not int or transaction_info["fee"] < 0:
        raise ProofRejected("invalid receipt fee")
    if type(attestation) is not dict or set(attestation) != {
        "network", "source", "txid", "block_number", "block_id",
        "solidified", "authenticated", "genesis_verified",
        "transaction_endpoint", "receipt_endpoint",
    }:
        raise ProofRejected("independent node provenance missing")
    if (attestation["network"] != NETWORK or
        attestation["source"] != "independent-solidity-node" or
        attestation["txid"] != txid or
        attestation["transaction_endpoint"] != "/walletsolidity/gettransactionbyid" or
        attestation["receipt_endpoint"] != "/walletsolidity/gettransactioninfobyid"):
        raise ProofRejected("wrong independent chain evidence")
    if any(attestation[k] is not True for k in
           ("solidified", "authenticated", "genesis_verified")):
        raise ProofRejected("independent finality not established")
    if (type(attestation["block_number"]) is not int or
        attestation["block_number"] != transaction_info["blockNumber"] or
        type(attestation["block_id"]) is not str or
        re.fullmatch(r"[0-9a-f]{64}", attestation["block_id"]) is None):
        raise ProofRejected("solidified block evidence mismatch")
    # Do not trust optional contractRet if supplied: reject failures, but
    # never infer success from absence. The receipt SUCCESS is mandatory.
    ret = transaction.get("ret")
    if ret is not None and (type(ret) is not list or len(ret) != 1 or
                            ret[0].get("contractRet") != "SUCCESS"):
        raise ProofRejected("transaction execution failed")
    evidence = {
        "order": order, "transaction": transaction,
        "transaction_info": transaction_info, "attestation": attestation,
    }
    digest = sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()
    return NativeTransferEvidence(
        network=NETWORK, txid=txid, order_ref=order["order_ref"],
        enrollment_ref=order["enrollment_ref"], recipient_hex=owner_receiver_hex,
        amount_sun=AMOUNT_SUN, solidity_block_number=attestation["block_number"],
        solidity_block_id=attestation["block_id"], evidence_sha256=digest,
    )
