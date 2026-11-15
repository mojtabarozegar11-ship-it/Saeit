#!/usr/bin/env python3
"""One bounded read-only, independent Mainnet SolidityNode receipt verification.

Queries at most ONE existing verified paid walletless TRX transaction, at most
TWO HTTP read methods, through exact https://api.trongrid.io only. No keys,
wallet sends, broadcasts, purchase, DB writes, user details, transaction hashes
or amounts printed. Failed/empty/429 provider results remain UNKNOWN, not fraud
or zero receipts. Does not grant entitlement or attest real external buyers.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path("/home/zomorod2/Saeit-staging")
OWNER_RECEIVER = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
PROVIDER = "mpw_walletless_trx_v1"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX41 = re.compile(r"41[0-9a-f]{40}\Z")
API = "https://api.trongrid.io"
MAX_RESPONSE = 100_000
TIMEOUT_SEC = 9
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58check_to_hex(value):
    if type(value) is not str or len(value) != 34:
        raise ValueError("wrong Base58 address")
    integer = 0
    for char in value:
        if char not in B58:
            raise ValueError("invalid Base58 alphabet")
        integer = integer * 58 + B58.index(char)
    raw = integer.to_bytes(25, "big")
    if (raw[0] != 0x41 or raw[-4:] != hashlib.sha256(
            hashlib.sha256(raw[:21]).digest()
    ).digest()[:4]):
        raise ValueError("Base58Check mismatch")
    return raw[:21].hex()


def compare_solidified(body, receipt, *, txid, payer, receiver, sun):
    """Compare native TRX body+receipt with saved merchant ledger references."""
    if (type(txid) is not str or HEX64.fullmatch(txid) is None
            or type(payer) is not str or HEX41.fullmatch(payer) is None
            or type(receiver) is not str or HEX41.fullmatch(receiver) is None
            or type(sun) is not int or sun <= 0):
        return False
    if not isinstance(body, dict) or not isinstance(receipt, dict):
        return False
    if body.get("Error") or receipt.get("Error"):
        return False
    if body.get("txID") != txid or receipt.get("id") != txid:
        return False
    ret = body.get("ret")
    if type(ret) is not list or len(ret) != 1 or not isinstance(ret[0], dict):
        return False
    if ret[0].get("contractRet") != "SUCCESS":
        return False
    raw = body.get("raw_data")
    if not isinstance(raw, dict):
        return False
    contracts = raw.get("contract")
    if type(contracts) is not list or len(contracts) != 1:
        return False
    contract = contracts[0]
    if not isinstance(contract, dict) or contract.get("type") != "TransferContract":
        return False
    param = contract.get("parameter")
    if not isinstance(param, dict):
        return False
    if param.get("type_url") not in (
        None, "type.googleapis.com/protocol.TransferContract"
    ):
        return False
    data = param.get("value")
    if (not isinstance(data, dict)
            or data.get("owner_address") != payer
            or data.get("to_address") != receiver
            or type(data.get("amount")) is not int or data["amount"] != sun
            or payer == receiver):
        return False
    if (type(receipt.get("blockNumber")) is not int or receipt["blockNumber"] <= 0
            or type(receipt.get("blockTimeStamp")) is not int
            or receipt["blockTimeStamp"] <= 0
            or receipt.get("result") in ("FAILED", "FAILURE")):
        return False
    execution = receipt.get("receipt")
    if not isinstance(execution, dict) or execution.get("result") not in (
        None, "SUCCESS"
    ):
        return False
    return True


def _one_solidified_node_read(path, txid):
    """Allowlisted endpoint, no proxy/redirect, one read-only RPC HTTP POST."""
    import urllib.request
    if path not in ("/walletsolidity/gettransactionbyid",
                    "/walletsolidity/gettransactioninfobyid"):
        raise ValueError("only read-only Solidity methods allowed")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise ValueError("unexpected RPC redirect")

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect()
    )
    request = urllib.request.Request(
        API + path, method="POST",
        data=json.dumps({"value": txid}, separators=(",", ":")).encode("ascii"),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json"},
    )
    with opener.open(request, timeout=TIMEOUT_SEC) as res:
        if res.status != 200:
            raise ValueError("RPC transport not successful")
        raw = res.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError("RPC result too large")
    result = json.loads(raw.decode("utf-8"))
    if type(result) is not dict or result.get("Error"):
        raise ValueError("RPC returned no usable result")
    return result


def _select_one_existing_paid():
    from core.models import LedgerEntry, PaymentIntent, PaymentWebhookEvent
    from core.crown_tron_receipts import verified_walletless_credit
    paid = PaymentIntent.objects.filter(
        provider=PROVIDER, status="paid",
    ).select_related("order__customer").order_by("pk")
    # Limit any database scanning to 25 candidate orders in this run.
    for intent in paid[:25]:
        if (intent.order.customer.is_staff is True
                or intent.order.customer.is_superuser is True):
            continue
        if not verified_walletless_credit(intent.order, intent):
            continue
        if LedgerEntry.objects.filter(
            order_id=intent.order_id,
            entry_type__in=("refund", "reversal", "chargeback"),
        ).exists():
            continue
        events = list(PaymentWebhookEvent.objects.filter(
            payment_intent_id=intent.pk, provider=PROVIDER,
            status="processed", event_type="tron_finalized",
        )[:2])
        if len(events) != 1:
            continue
        txid = events[0].event_id
        if type(txid) is not str or HEX64.fullmatch(txid) is None:
            continue
        doc = json.loads(intent.provider_reference)
        if (type(doc) is not dict or doc.get("to") != OWNER_RECEIVER
                or type(doc.get("sun")) is not int or doc["sun"] <= 0):
            continue
        ledgers = list(LedgerEntry.objects.filter(
            order_id=intent.order_id, payment_intent_id=intent.pk,
            entry_type="credit",
        )[:2])
        if len(ledgers) != 1:
            continue
        metadata = ledgers[0].metadata
        if not isinstance(metadata, dict):
            continue
        sender = metadata.get("sender")
        if type(sender) is not str:
            continue
        try:
            payer = base58check_to_hex(sender)
            receiver = base58check_to_hex(OWNER_RECEIVER)
        except (ValueError, OverflowError):
            continue
        return (txid, payer, receiver, doc["sun"])
    return None


def main():
    result = {
        "schema": "mpw.tron.one_prior_payment.solidity.readonly.v1",
        "read_only": True, "verified_existing_paid_candidate_found": False,
        "mainnet_solidity_body_present": False,
        "mainnet_solidity_receipt_present": False,
        "same_amount_receiver_sender_txid_solidified": False,
        "independent_node_check_performed": False,
        "scope": "at_most_one_prior_nonstaff_receipt",
        "provider_error_type": None,
        "no_paid_checkout_or_broadcast": True,
        "no_customer_delivery_asserted": True,
        "actual_external_buyer_proven": False,
    }
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve() != ROOT:
        result["provider_error_type"] = "UntrustedTenant"
    else:
        try:
            os.chdir(ROOT)
            sys.path.insert(0, str(ROOT))
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
            import django
            django.setup()
            item = _select_one_existing_paid()
            if item is not None:
                result["verified_existing_paid_candidate_found"] = True
                txid, payer, receiver, amount = item
                body = _one_solidified_node_read(
                    "/walletsolidity/gettransactionbyid", txid)
                result["mainnet_solidity_body_present"] = (
                    body.get("txID") == txid
                )
                receipt = _one_solidified_node_read(
                    "/walletsolidity/gettransactioninfobyid", txid)
                result["mainnet_solidity_receipt_present"] = (
                    receipt.get("id") == txid
                )
                result["independent_node_check_performed"] = True
                result["same_amount_receiver_sender_txid_solidified"] = (
                    compare_solidified(
                        body, receipt, txid=txid, payer=payer,
                        receiver=receiver, sun=amount,
                    )
                )
        except Exception as exc:
            # No HTTP/transport errors, addresses, RPC bodies or txIDs leaked.
            result["provider_error_type"] = type(exc).__name__
    print("MPW_TRON_PRIOR_RECEIPT_SOLIDITY_READONLY="
          + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
