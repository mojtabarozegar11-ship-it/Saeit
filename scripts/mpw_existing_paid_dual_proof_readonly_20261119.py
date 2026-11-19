"""Recheck existing paid receipts with two pinned nodes. No settlement or delivery writes."""
import json
import os
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = Path("/home/zomorod2/Saeit-staging")
LIMIT = 3


def run():
    report = {"read_only": True, "historical_paid_present": False,
              "dual_proof_matches": 0, "verified_receipts": 0,
              "private_files_available": 0, "digital_grants_present": 0,
              "review_complete": False, "new_payment_created": False,
              "operator_independence_attested": False, "errors": {}}
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve() != ROOT:
        report["errors"]["root"] = "unavailable"
        return report
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        import django
        django.setup()
        from core.models import PaymentIntent, PaymentWebhookEvent, OrderItem, LedgerEntry
        from core.crown_tron_receipts import verified_walletless_credit
        from mpw_commerce.models import CommerceFulfillment, CommerceInvoice
        from mpw_commerce.downloads import _private_file
        from services.mpw_walletless_commercial_intent import _decode, PROVIDER
        from services.mpw_tron_independent_solidified_rpc import RpcProvider, query_solidified_transfer
        from services.mpw_trx_walletless_core import verify_two_source_transfer
    except Exception as exc:
        report["errors"]["setup"] = type(exc).__name__
        return report
    nodes = (
        RpcProvider("publicnode-allnodes", "allnodes", "https://tron-solidity-rpc.publicnode.com"),
        RpcProvider("trongrid", "trongrid", "https://api.trongrid.io"),
    )
    try:
        rows = list(PaymentIntent.objects.filter(provider=PROVIDER, status="paid")
                    .select_related("order").order_by("pk")[:LIMIT+1])
        report["historical_paid_present"] = bool(rows)
        report["review_complete"] = len(rows) <= LIMIT
        for intent in rows[:LIMIT]:
            try:
                if not verified_walletless_credit(intent.order, intent):
                    continue
                report["verified_receipts"] += 1
                items = list(OrderItem.objects.filter(order=intent.order).select_related("product")[:2])
                if len(items) == 1:
                    item = items[0]
                    grant = CommerceFulfillment.objects.filter(
                        item=item, kind="digital", status__in=("ready", "complete")).exists()
                    report["digital_grants_present"] += int(grant)
                    try:
                        asset = _private_file(item)
                        report["private_files_available"] += int(asset.is_file() and not asset.is_symlink())
                    except (OSError, ValueError):
                        pass
                if CommerceInvoice.objects.filter(order=intent.order).exists():
                    continue
                event = PaymentWebhookEvent.objects.get(
                    payment_intent=intent, provider=PROVIDER, event_type="tron_finalized", status="processed")
                credit = LedgerEntry.objects.get(order=intent.order, payment_intent=intent, entry_type="credit")
                invoice = _decode(intent)
                # The sole outbound value is an already-public blockchain transaction hash.
                with ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(executor.map(lambda node: query_solidified_transfer(node, event.event_id), nodes))
                # Historical proof comparison, not authorization to settle/reuse this hash.
                hash_value, sender = verify_two_source_transfer(invoice, *results,
                    tx_previously_consumed=lambda network, tx: tx != event.event_id)
                if hash_value == event.event_id and sender == credit.metadata.get("sender"):
                    report["dual_proof_matches"] += 1
            except Exception as exc:
                key = type(exc).__name__
                report["errors"][key] = report["errors"].get(key, 0)+1
    except Exception as exc:
        report["errors"]["inventory"] = type(exc).__name__
    return report


if __name__ == "__main__":
    print("MPW_EXISTING_DUAL_PROOF_READONLY="+json.dumps(run(), sort_keys=True))
