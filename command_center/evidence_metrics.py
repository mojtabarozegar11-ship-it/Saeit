"""Read-only, attributed operational counts for staff; never infer earned revenue.

Important: core models may be shared by multiple products/sites, and database task
completion is not proof of a VPS factory running or external merchant settlement.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .factory_status import read_factory_status

from core.models import (
    Agent, AgentTask, ApprovalRequest, EducationEnrollment, Order, PaymentIntent, Product,
)


def _status_counts(model):
    return {
        str(item["status"]): item["total"]
        for item in model.objects.values("status").annotate(total=Count("pk"))
    }


@staff_member_required
@require_GET
def evidence_metrics(request):
    result = {
        "captured_at": timezone.now().isoformat(),
        "source": "cPanel live Django MySQL: core tables",
        "scope": "shared_core_models_not_proven_exclusive_to_mojplaywin",
        "agents": {
            "registered": Agent.objects.count(),
            "enabled_in_db": Agent.objects.filter(active=True).count(),
            "tasks": {"total": AgentTask.objects.count(), "by_status": _status_counts(AgentTask)},
            "runtime_state": "unknown",
            "runtime_state_reason": "database_state_is_not_live_worker_evidence",
        },
        "approvals": {
            "pending": ApprovalRequest.objects.filter(status="pending").count(),
        },
        "catalog": {
            "products": Product.objects.count(),
            "active_products": Product.objects.filter(active=True).count(),
            "verified_marketplace_publications": None,
        },
        "orders": {
            "total": Order.objects.count(),
            "by_status": _status_counts(Order),
        },
        "payments": {
            "intents": PaymentIntent.objects.count(),
            "by_status": _status_counts(PaymentIntent),
            "verified_mainnet_settlements": None,
        },
        "education": {"enrollment_records": EducationEnrollment.objects.count()},
        "revenue": {
            "verified_amounts_by_currency": None,
            "state": "unknown",
            "reason": "no_independent_merchant_settlement_reconciliation",
        },
        "factory": read_factory_status(),
    }
    response = JsonResponse(result, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    return response
