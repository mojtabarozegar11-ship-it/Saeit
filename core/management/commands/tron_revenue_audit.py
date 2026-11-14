"""Private read-only TRX receipt audit for one organizational bot.

No customers' emails, personal data, wallet sender or transaction hashes are
printed. 'Verified' means backed by the persisted finalized-node proof event
and exactly one matching ledger credit, not merely invoice status='paid'.
"""
from collections import defaultdict
from decimal import Decimal
import json

from django.core.management.base import BaseCommand

from core.models import LedgerEntry, PaymentWebhookEvent
from core.tron_gateway_invoice import TronGatewayInvoice
from core.tron_gateway_web import PROVIDER
from core.tron_gateway_verify import MAINNET_RECEIVER


class Command(BaseCommand):
    help = "Read-only private revenue evidence by host/currency (no PII)"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=5000)

    def handle(self, *args, **options):
        limit = options["limit"]
        if type(limit) is not int or not 1 <= limit <= 20000:
            raise ValueError("Invalid bounded revenue audit limit")
        invoices = list(TronGatewayInvoice.objects.select_related(
            "order", "payment_intent").order_by("-pk")[:limit + 1])
        truncated = len(invoices) > limit
        invoices = invoices[:limit]
        paid_ids = [i.payment_intent_id for i in invoices if i.status == "paid"]
        events = defaultdict(list)
        credits = defaultdict(list)
        if paid_ids:
            for event in PaymentWebhookEvent.objects.filter(
                    provider=PROVIDER, payment_intent_id__in=paid_ids):
                events[event.payment_intent_id].append(event)
            for credit in LedgerEntry.objects.filter(
                    payment_intent_id__in=paid_ids, entry_type="credit"):
                credits[credit.payment_intent_id].append(credit)
        result = {
            "scope": "private-read-only-chain-backed-ledger",
            "complete": not truncated,
            "scanned": len(invoices),
            "pending": 0,
            "paid_evidenced": 0,
            "paid_without_complete_evidence": 0,
            "by_host_currency": {},
        }
        group = defaultdict(lambda: {"invoice_count": 0, "paid_evidenced": 0,
                                     "gross_catalog_units": Decimal("0"),
                                     "received_trx": Decimal("0")})
        for inv in invoices:
            groupkey = (inv.source_host, inv.order.currency)
            g = group[groupkey]
            g["invoice_count"] += 1
            if inv.status != "paid":
                result["pending"] += 1
                continue
            matching_events = [
                e for e in events.get(inv.payment_intent_id, ())
                if e.event_id == inv.txid and e.payload_hash == inv.proof_digest
                and e.status == "processed" and e.event_type == "tron_finalized"
            ]
            matching_credits = [
                c for c in credits.get(inv.payment_intent_id, ())
                if c.order_id == inv.order_id and
                c.reference == "tron-mainnet:" + (inv.txid or "") and
                c.amount == inv.order.total and c.currency == inv.order.currency and
                type(c.metadata) is dict and
                c.metadata.get("receiver") == MAINNET_RECEIVER and
                c.metadata.get("amount_sun") == inv.amount_sun and
                c.metadata.get("proof_digest") == inv.proof_digest and
                c.metadata.get("source_host") == inv.source_host
            ]
            if (len(matching_events) == 1 and len(matching_credits) == 1 and
                    inv.payment_intent.status == "paid" and
                    inv.payment_intent.order_id == inv.order_id and
                    inv.order.status == "paid" and inv.txid and inv.proof_digest):
                result["paid_evidenced"] += 1
                g["paid_evidenced"] += 1
                g["gross_catalog_units"] += inv.order.total
                g["received_trx"] += Decimal(inv.amount_sun) / Decimal(1000000)
            else:
                result["paid_without_complete_evidence"] += 1
        for (host, currency), groupdata in sorted(group.items()):
            result["by_host_currency"][host + "|" + currency] = {
                "invoice_count": groupdata["invoice_count"],
                "paid_evidenced": groupdata["paid_evidenced"],
                "gross_catalog_units": str(groupdata["gross_catalog_units"]),
                "native_trx_received": str(groupdata["received_trx"]),
            }
        self.stdout.write("TRON_REVENUE_EVIDENCE=" + json.dumps(
            result, ensure_ascii=False, sort_keys=True))
