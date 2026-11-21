"""Fail-closed, OFFLINE Plan1 settlement ledger prototype; never opens checkout.

This component cannot authorize sale, fetch chain data, issue a payable invoice,
sign a receipt, refund funds, or activate a challenge. SQLite is a reference
transactional implementation; production must use the SAME durable global
network+txid uniqueness constraint shared with every product/payment rail.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from hashlib import sha256

NETWORK = "tron-mainnet"
PRODUCT = "MOJ-PROP-01"
AMOUNT = 30_000_000
VERSION = "2026-11-15/v1.2"
REQUIRED = frozenset((
    "legal_sale", "broker_verified", "capital_reserved", "kyc_passed",
    "eligibility_passed", "buyer_contract_signed", "terms_digest_verified",
    "owner_wallet_verified", "restoration_drill_passed", "risk_approved",
    "jurisdiction_allowed", "buyer_identity_bound", "payer_bound",
    "order_authenticated", "invoice_immutable", "node_authenticated",
    "solidity_body_verified", "solidity_receipt_verified",
    "merchant_approved", "compliance_release",
))


class SettlementBlocked(ValueError):
    pass


def initialize(connection: sqlite3.Connection) -> None:
    """Initialize tables before transactions; never on an active checkout request."""
    connection.execute("""CREATE TABLE IF NOT EXISTS global_tron_tx_claims (
        network TEXT NOT NULL, txid TEXT NOT NULL,
        order_ref TEXT NOT NULL, product TEXT NOT NULL,
        amount_sun INTEGER NOT NULL, evidence_sha256 TEXT NOT NULL,
        PRIMARY KEY (network, txid), UNIQUE(order_ref),
        CHECK(network = 'tron-mainnet'), CHECK(amount_sun > 0)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS plan1_settlement_audit (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_ref TEXT NOT NULL, network TEXT NOT NULL,
        txid TEXT NOT NULL, evidence_sha256 TEXT NOT NULL,
        event_type TEXT NOT NULL CHECK(event_type = 'CANDIDATE_RESERVED')
    )""")
    connection.commit()


def _validate(candidate: Mapping, gates: Mapping, order: Mapping) -> tuple[str, str]:
    if not isinstance(candidate, Mapping) or not isinstance(gates, Mapping) or not isinstance(order, Mapping):
        raise SettlementBlocked("trusted inputs required")
    if set(gates) != REQUIRED or any(gates[k] is not True for k in REQUIRED):
        raise SettlementBlocked("all twenty independently verified gates required")
    if candidate.get("schema") != "mojprop.plan1.tron.match.v1":
        raise SettlementBlocked("wrong verifier schema")
    if candidate.get("candidate_matches_persisted_order") is not True:
        raise SettlementBlocked("no valid chain candidate")
    if candidate.get("buyer_entitlement_granted") is not False or candidate.get("revenue_booked") is not False:
        raise SettlementBlocked("candidate already mutated downstream state")
    if candidate.get("network") != NETWORK or candidate.get("product") != PRODUCT:
        raise SettlementBlocked("wrong chain or SKU")
    if type(candidate.get("amount_sun")) is not int or candidate["amount_sun"] != AMOUNT:
        raise SettlementBlocked("wrong native amount")
    if candidate.get("contract_version") != VERSION:
        raise SettlementBlocked("wrong contract version")
    if candidate.get("order_ref") != order.get("order_ref") or order.get("product") != PRODUCT:
        raise SettlementBlocked("order mismatch")
    if order.get("network") != NETWORK or order.get("contract_version") != VERSION:
        raise SettlementBlocked("order scope mismatch")
    if order.get("precontract_sha256") != candidate.get("precontract_sha256"):
        raise SettlementBlocked("terms digest mismatch")
    if order.get("amount_sun") != AMOUNT or type(order.get("amount_sun")) is not int:
        raise SettlementBlocked("persisted amount mismatch")
    if order.get("authenticated") is not True or order.get("payable_release") is not True:
        raise SettlementBlocked("no independently released authenticated order")
    txid = candidate.get("txid")
    ref = candidate.get("order_ref")
    digest = candidate.get("precontract_sha256")
    if not isinstance(txid, str) or len(txid) != 64 or any(c not in "0123456789abcdef" for c in txid):
        raise SettlementBlocked("invalid txid")
    if not isinstance(ref, str) or not ref.startswith("MOJPROP01-") or len(ref) > 42:
        raise SettlementBlocked("invalid order reference")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) or digest == "0"*64:
        raise SettlementBlocked("invalid terms digest")
    return ref, txid


def reserve_candidate(connection: sqlite3.Connection, *, candidate: Mapping,
                      gates: Mapping, order: Mapping) -> dict:
    """Atomic global reservation only; never credit, invoice, sign or activate.

    Caller must fetch all gates from trusted services, NOT HTTP request JSON.
    Never expose this function as a public route. Durable production deployment
    requires migration, concurrency tests, backup/restore and security review.
    """
    ref, txid = _validate(candidate, gates, order)
    evidence = json.dumps(dict(candidate), sort_keys=True, separators=(",", ":"), allow_nan=False)
    evidence_hash = sha256(evidence.encode("utf-8")).hexdigest()
    if connection.in_transaction:
        raise SettlementBlocked("caller transaction state is not isolated")
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO global_tron_tx_claims(network,txid,order_ref,product,amount_sun,evidence_sha256) VALUES (?,?,?,?,?,?)",
            (NETWORK, txid, ref, PRODUCT, AMOUNT, evidence_hash))
        connection.execute(
            "INSERT INTO plan1_settlement_audit(order_ref,network,txid,evidence_sha256,event_type) VALUES (?,?,?,?,?)",
            (ref, NETWORK, txid, evidence_hash, "CANDIDATE_RESERVED"))
        connection.commit()
    except (sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
        connection.rollback()
        raise SettlementBlocked("duplicate claim, duplicate order or unavailable durable ledger") from exc
    return {
        "status": "CANDIDATE_RESERVED_NOT_SETTLED",
        "order_ref": ref, "network": NETWORK, "txid": txid,
        "evidence_sha256": evidence_hash,
        "checkout_enabled": False, "receipt_signed": False,
        "revenue_booked": False, "challenge_activated": False,
        "refund_executed": False,
    }
