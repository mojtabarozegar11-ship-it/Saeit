"""Staff-only, read-only evidence-led management report."""

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.business_management import review_business
from core.management.commands.business_operating_review import collect_management_metrics


@staff_member_required
@require_GET
def business_review(request):
    metrics = collect_management_metrics()
    report = review_business(metrics)
    report.update({
        "generated_at": timezone.now().isoformat(),
        "scope": "local_django_database_only; external sources unverified",
        "metrics": metrics,
    })
    response = JsonResponse(report)
    response["Cache-Control"] = "no-store"
    return response
