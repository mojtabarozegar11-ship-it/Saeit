"""Run the virtual chief economist's evidence-led business-science cycle."""
import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.business_scientist import build_business_science_plan
from core.management.commands.business_operating_review import collect_management_metrics
from core.models import AuditLog


class Command(BaseCommand):
    help = "Produce an evidence-linked management and controlled-growth plan."

    def add_arguments(self, parser):
        parser.add_argument(
            "--record", action="store_true",
            help="Store a sanitized audit receipt for this planning cycle.",
        )

    def handle(self, *args, **options):
        metrics = collect_management_metrics()
        plan = build_business_science_plan(metrics)
        plan["generated_at"] = timezone.now().isoformat()
        plan["scope"] = (
            "connected_local_django_database_only; VPS factory, production sites, "
            "external market data, and independently settled cash remain unverified"
        )
        if options["record"]:
            receipt = AuditLog.objects.create(
                actor_type="system",
                actor_id="business-scientist-professor",
                action="business_scientist_cycle",
                target_type="operating_system",
                target_id="zomorod_mojplaywin",
                after_state={
                    "constraint": plan["next_experiment"]["constraint"],
                    "primary_measure": plan["next_experiment"]["primary_measure"],
                    "evidence_gaps": plan["evidence_gaps"],
                    "scope": plan["scope"],
                },
                trace_id=f"business-science-{timezone.now():%Y%m%d%H%M%S%f}",
            )
            plan["audit_id"] = receipt.pk
        self.stdout.write(json.dumps(plan, ensure_ascii=False, default=str, sort_keys=True))
