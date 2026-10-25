"""Read-only management cycle across the connected business database.

Use --record to save an audit receipt. Local application records are not
independent verification of external services or cash settlement.
"""
import json

from django.core.management.base import BaseCommand
from django.db.models import Count, Min, Sum
from django.utils import timezone

from core.business_management import observed, review_business, unknown
from core.models import (
    AgentTask, ApprovalRequest, AuditLog, LedgerEntry, Order, PaymentIntent, Product,
)


def collect_management_metrics():
    timestamp = timezone.now().isoformat()

    def measured(value, table):
        return observed(value, f"local_django:{table}", timestamp)

    now = timezone.now()
    task_flow = list(
        AgentTask.objects.values("action_type", "status")
        .annotate(count=Count("pk"), oldest_created=Min("created_at"))
        .order_by("action_type", "status")
    )
    for row in task_flow:
        oldest = row.pop("oldest_created")
        row["oldest_age_hours"] = (
            max(0, round((now - oldest).total_seconds() / 3600, 2))
            if oldest else None
        )

    order_pipeline = list(
        Order.objects.values("status", "currency")
        .annotate(count=Count("pk"), recorded_order_value=Sum("total"))
        .order_by("currency", "status")
    )
    intents = list(
        PaymentIntent.objects.values("provider", "status", "currency")
        .annotate(count=Count("pk"), intent_amount=Sum("amount"))
        .order_by("currency", "provider", "status")
    )
    ledger = list(
        LedgerEntry.objects.values("entry_type", "currency")
        .annotate(count=Count("pk"), recorded_amount=Sum("amount"))
        .order_by("currency", "entry_type")
    )
    catalog = list(
        Product.objects.filter(active=True).values("currency")
        .annotate(count=Count("pk"))
        .order_by("currency")
    )

    return {
        "queued_tasks": measured(AgentTask.objects.filter(status="queued").count(), "AgentTask"),
        "blocked_tasks": measured(AgentTask.objects.filter(status="blocked").count(), "AgentTask"),
        "active_products": measured(Product.objects.filter(active=True).count(), "Product"),
        "orders": measured(Order.objects.count(), "Order"),
        "pending_approvals": measured(ApprovalRequest.objects.filter(status="pending").count(), "ApprovalRequest"),
        "factory_flow": measured(task_flow, "AgentTask.action_type_status"),
        "order_pipeline": measured(order_pipeline, "Order.status_currency"),
        "payment_intents": measured(intents, "PaymentIntent.provider_status"),
        "ledger_activity": measured(ledger, "LedgerEntry.entry_type_currency"),
        "product_catalog": measured(catalog, "Product.active_currency"),
        "independently_validated_market": unknown("No independent buyer/competitor evidence adapter"),
        "verified_collected_cash": unknown("No provider/on-chain-to-ledger settlement reconciliation"),
        "accepted_factory_products": unknown("No independent factory acceptance receipts connected"),
        "site_health": unknown("No timestamped independent probes of both production sites"),
        "attributable_costs": unknown("Acquisition, refund, fee, and fulfillment costs are not reconciled by currency"),
    }


class Command(BaseCommand):
    help = "Evaluate scientific business bottlenecks without external or financial changes."

    def add_arguments(self, parser):
        parser.add_argument("--record", action="store_true", help="Store a sanitized review audit receipt")

    def handle(self, *args, **options):
        metrics = collect_management_metrics()
        report = review_business(metrics)
        report["generated_at"] = timezone.now().isoformat()
        report["scope"] = "local_django_database_only; external business sources remain unverified"
        report["metrics"] = metrics
        if options["record"]:
            receipt = AuditLog.objects.create(
                actor_type="system",
                actor_id="business-operating-review",
                action="business_operating_review",
                target_type="operating_system",
                target_id="zomorod_mojplaywin",
                after_state={
                    "next_constraint": report["next_constraint"],
                    "findings": report["findings"],
                    "unknown_metrics": report["unknown_metrics"],
                    "scope": report["scope"],
                },
                trace_id=f"business-review-{timezone.now():%Y%m%d%H%M%S%f}",
            )
            report["audit_id"] = receipt.pk
        self.stdout.write(json.dumps(report, ensure_ascii=False, default=str, sort_keys=True))
