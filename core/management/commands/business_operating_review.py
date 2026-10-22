"""Read-only management cycle across the connected business database.

Use --record to save an audit receipt.  This command never publishes, spends,
changes a payment destination, or claims external services are healthy.
"""

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.business_management import observed, review_business, unknown
from core.models import AgentTask, ApprovalRequest, AuditLog, Order, Product


def collect_management_metrics():
    timestamp = timezone.now().isoformat()

    def measured(value, table):
        return observed(value, f"local_django:{table}", timestamp)

    return {
        "queued_tasks": measured(AgentTask.objects.filter(status="queued").count(), "AgentTask"),
        "blocked_tasks": measured(AgentTask.objects.filter(status="blocked").count(), "AgentTask"),
        "active_products": measured(Product.objects.filter(active=True).count(), "Product"),
        "orders": measured(Order.objects.count(), "Order"),
        "pending_approvals": measured(ApprovalRequest.objects.filter(status="pending").count(), "ApprovalRequest"),
        "independently_validated_market": unknown("No external buyer/competitor evidence adapter"),
        "verified_collected_cash": unknown("Provider-to-ledger settled-cash reconciliation not connected"),
        "accepted_factory_products": unknown("VPS specialist receipts are not connected to this Django database"),
        "site_health": unknown("Production health requires timestamped independent probes"),
    }


class Command(BaseCommand):
    help = "Evaluate scientific business bottlenecks without making external or financial changes."

    def add_arguments(self, parser):
        parser.add_argument("--record", action="store_true", help="Store a sanitized review audit receipt")

    def handle(self, *args, **options):
        metrics = collect_management_metrics()
        report = review_business(metrics)
        report["generated_at"] = timezone.now().isoformat()
        report["scope"] = "local_django_database_only; global sites/VPS/payment providers unverified"
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
