#!/usr/bin/env python3
"""No-write production readiness probe for TWO authenticated TRON operators.

Credentials and the known-native-transfer canary belong in server secrets.
No endpoints, keys, wallets, amounts, hashes or raw RPC replies are printed.
Passing this probe does NOT authorize public checkout or real-money spending.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import sys
from pathlib import Path

# This script is also streamed over SSH as `python -`: the checked-out repo
# directory is not necessarily the interpreter's working directory.
APP=Path("/home/zomorod2/Saeit-staging")
if str(APP) not in sys.path:
    sys.path.insert(0,str(APP))

from services.mpw_tron_independent_solidified_rpc import (
    RpcProvider, PaymentHold, verify_distinct_provider_config,
    query_solidified_head, query_solidified_transfer,
)

TXID = re.compile(r"^[a-f0-9]{64}$")
FIELDS = ("SOURCE_ID", "OPERATOR_ID", "ENDPOINT", "API_KEY", "AUTH_HEADER")


def _provider(env, label):
    prefix="MPW_TRON_RPC_"+label+"_"
    fields=[env.get(prefix+field, "") for field in FIELDS]
    if any(type(v) is not str or not v for v in fields):
        raise PaymentHold("Incomplete RPC provider configuration")
    return RpcProvider(*fields[:4], api_key_header=fields[4])


def audit(env, *, now=None, head_probe=query_solidified_head,
          transfer_probe=query_solidified_transfer):
    """All diagnostics are fixed safe codes; return no user or provider data."""
    result={
        "scope":"tron-mainnet-native-trx-readonly",
        "status":"BLOCKED",
        "operator_independence_attested":False,
        "two_fresh_solidified_heads":False,
        "matching_native_transfer_body_and_receipts":False,
        "orders_created":0,"financial_writes":0,"public_payment_activated":False,
    }
    if env.get("MPW_TRON_RPC_INDEPENDENCE_REVIEWED") != "1":
        result["reason"]="independent_operator_review_missing"
        return result
    result["operator_independence_attested"]=True
    try:
        a=_provider(env,"A")
        b=_provider(env,"B")
        verify_distinct_provider_config(a,b)
    except (PaymentHold,TypeError,ValueError):
        result["reason"]="provider_configuration_unapproved"
        return result
    moment=now or datetime.now(timezone.utc)
    try:
        heads=(head_probe(a,now=moment),head_probe(b,now=moment))
        if any(type(h) is not int or h<=0 for h in heads):
            raise PaymentHold("Invalid head metadata")
    except Exception:
        result["reason"]="authenticated_solidified_head_unavailable"
        return result
    result["two_fresh_solidified_heads"]=True
    txid=env.get("MPW_TRON_RPC_CANARY_TXID", "")
    sender=env.get("MPW_TRON_RPC_CANARY_SENDER", "")
    receiver=env.get("MPW_TRON_RPC_CANARY_RECEIVER", "")
    sun=env.get("MPW_TRON_RPC_CANARY_AMOUNT_SUN", "")
    if (not isinstance(txid,str) or not TXID.fullmatch(txid)
        or not isinstance(sender,str) or not isinstance(receiver,str)
        or not isinstance(sun,str) or not sun.isascii() or not sun.isdecimal()
        or sun.startswith("0") or len(sun)>18):
        result["reason"]="verified_native_canary_missing"
        return result
    try:
        proofs=(transfer_probe(a,txid),transfer_probe(b,txid))
        if (proofs[0].source_id!=a.source_id or proofs[1].source_id!=b.source_id
            or any(p.tx_hash!=txid or p.network!="tron-mainnet"
                or p.sender!=sender or p.recipient!=receiver
                or p.amount_sun!=int(sun) or p.solidified is not True
                or p.transfer_contract is not True or p.execution_success is not True
                for p in proofs)
            or proofs[0].block_time!=proofs[1].block_time):
            raise PaymentHold("Two independently verified transfers disagree")
    except Exception:
        result["reason"]="independent_native_transaction_proof_failed"
        return result
    result["matching_native_transfer_body_and_receipts"]=True
    result["status"]="PROVIDER_PROOF_READY_ONLY"
    result["reason"]="live_money_and_delivery_acceptance_still_required"
    return result


def main():
    # The existing production Passenger layout is checked without reading any
    # payment data or creating buyer orders.
    import pwd
    site=Path("/home/zomorod2/mojplaywin.com")
    if (pwd.getpwuid(os.getuid()).pw_name!="zomorod2"
        or not APP.is_dir() or APP.is_symlink() or site.is_symlink()
        or "APP='/home/zomorod2/Saeit-staging'" not in
        (site/"passenger_wsgi.py").read_text("utf8","replace")):
        raise SystemExit("Unverified production context")
    print("MPW_TRON_AUTHENTICATED_READONLY="+json.dumps(audit(os.environ),sort_keys=True))


if __name__=="__main__":
    main()
