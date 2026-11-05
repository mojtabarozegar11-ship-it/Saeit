#!/usr/bin/env python3
"""Read-only, privacy-minimal independent solidity recheck of existing MPW paid TRX.

No orders, ledger entries, payments, downloads, messages or production files
are created/changed. Only aggregate counts appear in output. A paid database
flag is never treated as independent Mainnet proof.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP = Path("/home/zomorod2/Saeit-staging")
ACK = "mpw-existing-paid-trx-readonly-20261105"


def run():
    if os.environ.get("MPW_READONLY_CHAIN_ACK") != ACK:
        raise RuntimeError("CHAIN_AUDIT_NOT_ARMED")
    if not APP.is_dir() or APP.is_symlink() or APP.resolve() != APP:
        raise RuntimeError("CHAIN_AUDIT_APP_ROOT_UNSAFE")
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    django.setup()
    from core.models import LedgerEntry, PaymentIntent, PaymentWebhookEvent
    from core.crown_tron_receipts import PROVIDER, verified_walletless_credit
    from f41_tron_mainnet_check import body, check_trx, tron_hex

    qs = PaymentIntent.objects.filter(
        provider=PROVIDER, status="paid"
    ).select_related("order").order_by("pk")
    total = qs.count()
    if total > 10:
        raise RuntimeError("CHAIN_AUDIT_SCOPE_EXCEEDS_TEN")
    counts = {
        "paid_intents": total,
        "local_receipts_verified": 0,
        "unique_transaction_ids": 0,
        "mainnet_solidified_matches": 0,
        "sender_matches": 0,
        "chain_mismatches": 0,
        "local_mismatches": 0,
        "rpc_unavailable": 0,
    }
    hashes = set()
    for intent in qs:
        if not verified_walletless_credit(intent.order, intent):
            counts["local_mismatches"] += 1
            continue
        counts["local_receipts_verified"] += 1
        event = PaymentWebhookEvent.objects.get(
            payment_intent=intent, provider=PROVIDER,
            event_type="tron_finalized", status="processed"
        )
        txid = event.event_id
        if txid in hashes:
            counts["chain_mismatches"] += 1
            continue
        hashes.add(txid)
        reference = json.loads(intent.provider_reference)
        invoice = {"recipient": reference["to"],
                   "amount_base_units": str(reference["sun"])}
        try:
            result = body(txid)
            _, ok = check_trx(invoice, txid, result)
            credit = LedgerEntry.objects.get(
                order=intent.order, payment_intent=intent, entry_type="credit"
            )
            sender = credit.metadata.get("sender", "") if isinstance(credit.metadata, dict) else ""
            contract = result.get("raw_data", {}).get("contract", [{}])[0]
            fields = contract.get("parameter", {}).get("value", {})
            sender_ok = bool(ok and fields.get("owner_address", "").lower()
                             == tron_hex(sender))
            if ok:
                counts["mainnet_solidified_matches"] += 1
            else:
                counts["chain_mismatches"] += 1
            if sender_ok:
                counts["sender_matches"] += 1
            elif ok:
                counts["chain_mismatches"] += 1
        except (OSError, TimeoutError, ValueError, TypeError, KeyError, IndexError) as exc:
            # Never print addresses, hashes, URLs, raw RPC data, email or buyer IDs.
            if type(exc).__name__ in ("TimeoutError", "HTTPError", "URLError", "OSError"):
                counts["rpc_unavailable"] += 1
            else:
                counts["chain_mismatches"] += 1
    counts["unique_transaction_ids"] = len(hashes)
    counts["readonly"] = True
    counts["customer_identifiers_logged"] = False
    counts["production_writes"] = False
    counts["source"] = "tron-mainnet-solidity-node"
    counts["acceptance"] = (
        "PASS" if total > 0 and
        counts["local_receipts_verified"] == total and
        counts["unique_transaction_ids"] == total and
        counts["mainnet_solidified_matches"] == total and
        counts["sender_matches"] == total and
        counts["chain_mismatches"] == 0 and
        counts["local_mismatches"] == 0 and
        counts["rpc_unavailable"] == 0 else "NOT_PROVEN"
    )
    print("MPW_PAID_CHAIN_READONLY=" + json.dumps(counts, sort_keys=True))
    return 0 if counts["acceptance"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(run())
