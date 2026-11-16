"""Moj Prop REAL funded Plan1: native-TRX match *candidate*, no RPC or credit.

This module never creates an invoice, broadcasts a transaction, enables a sale,
stores an order, calls external services or grants entitlement. A trusted server
must independently authenticate the buyer, issue an immutable seller-approved
invoice, query TWO authenticated TRON-mainnet /walletsolidity endpoints, and
commit the candidate txID to a UNIQUE ledger row atomically before credit.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Mapping

from services.mpw_trx_merchant_binding import validate_tron_recipient
from services.mojtaba_tron_owner_receiver import approved_recipient

PRODUCT = "MOJ-PROP-01"
CONTRACT_VERSION = "2026-11-15/v1.2"
NATIVE_AMOUNT_SUN = 30_000_000  # Exactly 30 native TRX; 1 TRX = 1e6 sun.
MERCHANT_DOMAIN = "mojplaywin.com"
MERCHANT_ID = "mojplaywin-store"
NETWORK = "tron-mainnet"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX41 = re.compile(r"41[0-9a-f]{40}\Z")
REFERENCE = re.compile(r"MOJPROP01-[A-Z0-9]{12,32}\Z")
ACCEPTANCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}\Z")
_SOLIDIFIED_BODY = "/walletsolidity/gettransactionbyid"
_SOLIDIFIED_RECEIPT = "/walletsolidity/gettransactioninfobyid"


class NativeTRXMatchRejected(ValueError):
    """A submitted chain observation cannot be applied to this buyer order."""


@dataclass(frozen=True)
class Plan1PersistedInvoice:
    """Hypothetical trusted persisted snapshot; NEVER build from browser fields.

    No part of this module issues the required real buyer order or checks
    the signed pre-contract digest against independent source-of-truth evidence.
    """

    product: str
    order_ref: str
    merchant_domain: str
    merchant_id: str
    network: str
    recipient: str
    amount_sun: int
    issued_at_sec: int
    expires_at_sec: int
    buyer_terms_acceptance: str
    contract_version: str
    precontract_sha256: str
    payer_hex41: str | None = None


def _hex_recipient(address: str) -> str:
    """Canonical Base58Check -> 0x41 + 20-byte hex; checksum verified first."""
    validate_tron_recipient(address)
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    num = 0
    for ch in address:
        num = num * 58 + alphabet.index(ch)
    raw = num.to_bytes(25, "big")
    return raw[:21].hex()


def validate_persisted_order(invoice: Plan1PersistedInvoice) -> None:
    """Reject forged/mis-scoped order snapshots before chain matching."""
    if type(invoice) is not Plan1PersistedInvoice:
        raise NativeTRXMatchRejected("expected server-persisted invoice snapshot")
    if (invoice.product != PRODUCT
            or invoice.merchant_domain != MERCHANT_DOMAIN
            or invoice.merchant_id != MERCHANT_ID
            or invoice.network != NETWORK
            or type(invoice.order_ref) is not str
            or not REFERENCE.fullmatch(invoice.order_ref)):
        raise NativeTRXMatchRejected("wrong SKU, unique order or merchant")
    if type(invoice.amount_sun) is not int or invoice.amount_sun != NATIVE_AMOUNT_SUN:
        raise NativeTRXMatchRejected("requires exactly 30 native TRX in sun")
    if (type(invoice.issued_at_sec) is not int
            or type(invoice.expires_at_sec) is not int
            or invoice.issued_at_sec < 1_500_000_000
            or not 0 < invoice.expires_at_sec - invoice.issued_at_sec <= 86_400):
        raise NativeTRXMatchRejected("invalid bounded invoice lifetime")
    if (type(invoice.buyer_terms_acceptance) is not str
            or ACCEPTANCE.fullmatch(invoice.buyer_terms_acceptance) is None):
        raise NativeTRXMatchRejected("independent buyer terms evidence missing")
    # A digest and buyer token are only *claims* in the persisted snapshot.
    # The order service MUST independently verify customer-signed terms,
    # identity, legal/treasury/broker clearance and bind the signed FA+EN
    # disclosure digest before issuing a payable invoice. This pure matcher
    # cannot do so and never credits a sale.
    if (type(invoice.contract_version) is not str
            or invoice.contract_version != CONTRACT_VERSION
            or type(invoice.precontract_sha256) is not str
            or HEX64.fullmatch(invoice.precontract_sha256) is None
            or invoice.precontract_sha256 == "0" * 64):
        raise NativeTRXMatchRejected("missing exact v1.2 signed-disclosure claim")
    try:
        _hex_recipient(invoice.recipient)
        # A syntactically valid Base58Check address can belong to a STRANGER.
        # Match the QR-verified owner recipient, never a buyer-supplied or
        # stale persisted recipient. No RPC or invoice/payment activation.
        if invoice.recipient != approved_recipient():
            raise NativeTRXMatchRejected("recipient is not the owner-approved wallet")
    except (ValueError, TypeError, OverflowError) as exc:
        raise NativeTRXMatchRejected("invalid or unauthorized owner recipient") from exc
    if (invoice.payer_hex41 is not None
            and (type(invoice.payer_hex41) is not str or
                 HEX41.fullmatch(invoice.payer_hex41) is None)):
        raise NativeTRXMatchRejected("invalid pre-registered payer")


def assess_solidified_native_transfer(
    invoice: Plan1PersistedInvoice,
    *,
    txid: str,
    solidity_transaction: Mapping,
    solidity_receipt: Mapping,
    body_endpoint: str,
    receipt_endpoint: str,
    trusted_node_network: str,
    already_assigned_txids: frozenset[str],
) -> dict:
    """Pure, fail-closed *candidate* matching. Never marks a ledger payment.

    Invoke only after separately authenticating a mainnet SolidityNode, the
    buyer's receipt claim and the invoiced merchant's receiving address.
    Block timestamp (not user-provided transaction creation timestamp) must
    fall inside the invoice validity window. The txID replay set is advisory:
    the actual DB must have a GLOBAL UNIQUE(network, txid) constraint across
    ALL products and an atomic compare-and-set; SKU-specific ledger tables
    and buyer-submitted txids alone are not reliable payment proof.
    """
    validate_persisted_order(invoice)
    if (type(txid) is not str or HEX64.fullmatch(txid) is None
            or type(body_endpoint) is not str or body_endpoint != _SOLIDIFIED_BODY
            or type(receipt_endpoint) is not str or receipt_endpoint != _SOLIDIFIED_RECEIPT
            or type(trusted_node_network) is not str or trusted_node_network != NETWORK):
        raise NativeTRXMatchRejected("unverified mainnet SolidityNode source")
    if (type(already_assigned_txids) is not frozenset
            or txid in already_assigned_txids):
        raise NativeTRXMatchRejected("txID is already assigned or replay state missing")
    if not isinstance(solidity_transaction, Mapping) or not isinstance(solidity_receipt, Mapping):
        raise NativeTRXMatchRejected("missing solidified transaction or receipt")
    # A node error field is a failure even if its value is empty, None, zero
    # or false; accepting a falsey error body could misclassify finality.
    if "Error" in solidity_transaction or "Error" in solidity_receipt:
        raise NativeTRXMatchRejected("node returned an error, not finality")
    if solidity_transaction.get("txID") != txid or solidity_receipt.get("id") != txid:
        raise NativeTRXMatchRejected("txID disagreement")
    raw = solidity_transaction.get("raw_data")
    if not isinstance(raw, Mapping):
        raise NativeTRXMatchRejected("missing native transfer body")
    contracts = raw.get("contract")
    if type(contracts) is not list or len(contracts) != 1:
        raise NativeTRXMatchRejected("unexpected transfer count")
    item = contracts[0]
    if not isinstance(item, Mapping) or item.get("type") != "TransferContract":
        raise NativeTRXMatchRejected("not a native TRX TransferContract")
    param = item.get("parameter")
    if not isinstance(param, Mapping) or param.get("type_url") not in (
            None, "type.googleapis.com/protocol.TransferContract"):
        raise NativeTRXMatchRejected("wrong transfer protocol")
    values = param.get("value")
    if not isinstance(values, Mapping):
        raise NativeTRXMatchRejected("missing transfer fields")
    payer = values.get("owner_address")
    recipient = values.get("to_address")
    amount = values.get("amount")
    if (type(payer) is not str or HEX41.fullmatch(payer) is None
            or type(recipient) is not str or HEX41.fullmatch(recipient) is None
            or payer == recipient or recipient != _hex_recipient(invoice.recipient)
            or type(amount) is not int or amount != NATIVE_AMOUNT_SUN):
        raise NativeTRXMatchRejected("recipient, sender or exact 30 TRX mismatch")
    ret = solidity_transaction.get("ret")
    if (type(ret) is not list or len(ret) != 1
            or not isinstance(ret[0], Mapping)
            or ret[0].get("contractRet") != "SUCCESS"):
        raise NativeTRXMatchRejected("native transaction did not complete successfully")
    if (solidity_receipt.get("result") not in (None, "SUCCESS")
            or not isinstance(solidity_receipt.get("receipt"), Mapping)
            or solidity_receipt["receipt"].get("result") not in (None, "SUCCESS")):
        raise NativeTRXMatchRejected("failed solidified execution")
    block = solidity_receipt.get("blockNumber")
    millis = solidity_receipt.get("blockTimeStamp")
    if (type(block) is not int or block <= 0 or type(millis) is not int
            or millis < invoice.issued_at_sec * 1000
            or millis >= invoice.expires_at_sec * 1000):
        raise NativeTRXMatchRejected("missing block proof or late/early payment")
    if invoice.payer_hex41 is None or payer != invoice.payer_hex41:
        # A shared receiver and common 30 TRX amount alone cannot assign a
        # stranger's public transaction to a particular buyer's order.
        raise NativeTRXMatchRejected("payer ownership not pre-bound to this buyer")
    return {
        "schema": "mojprop.plan1.tron.match.v1",
        "contract_version": CONTRACT_VERSION,
        "precontract_sha256": invoice.precontract_sha256,
        "product": PRODUCT,
        "order_ref": invoice.order_ref,
        "txid": txid,
        "amount_sun": NATIVE_AMOUNT_SUN,
        "network": NETWORK,
        "candidate_matches_persisted_order": True,
        "requires_atomic_unique_ledger_assignment": True,
        "buyer_entitlement_granted": False,
        "receipt_sent": False,
        "revenue_booked": False,
        "node_authentication_proven_by_this_module": False,
        "merchant_legal_release_proven_by_this_module": False,
    }
