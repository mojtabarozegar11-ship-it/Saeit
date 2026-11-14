"""Read-only first-party service lead funnel for the owner desk.

This is an operational SLA/triage endpoint, not an order/payment endpoint.
All values are aggregate counts; no customer PII or invoice data leaves CRM.
"""
from datetime import timedelta

from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.company_inquiry_models import CompanyInquiry
from core.service_quote_draft import (
    BOT_ID, DRAFT_MARKER, KIND_BY_CODE, SOURCE_MARKER, preview_candidates,
)
from core.service_intake_routing import service_intake_source_snapshot


def service_proposal_funnel_snapshot():
    """Measured DB counts plus explicitly unknown external-stage outcomes."""
    now = timezone.now()
    source = CompanyInquiry.objects.filter(
        internal_note__startswith=SOURCE_MARKER
    )
    scoped = {
        "bot": BOT_ID,
        "read_only": True,
        "privacy": "aggregates_only_no_customer_data",
        "source": "consented_django_service_leads_only",
        "source_configuration": service_intake_source_snapshot()["routing_mode"],
        "total_consent_provenance": source.count(),
        "new": source.filter(status="new").count(),
        "reviewing": source.filter(status="reviewing").count(),
        "approved": source.filter(status="approved").count(),
        "closed": source.filter(status="closed").count(),
        "draft_prepared_total": source.filter(
            internal_note__contains=DRAFT_MARKER
        ).count(),
        "awaiting_initial_review_over_24h": source.filter(
            status="new", created_at__lt=now - timedelta(hours=24)
        ).count(),
        "reviewing_over_72h": source.filter(
            status="reviewing", updated_at__lt=now - timedelta(hours=72)
        ).count(),
        "by_service": {},
        "cash_settled": None,
        "orders_delivered": None,
        "buyer_contact_verified": None,
        "price_approved": None,
        "php_live_health_verified": None,
        "production_release_approved": False,
    }
    for code, kind in KIND_BY_CODE.items():
        cohort = source.filter(
            kind=kind,
            subject__startswith=f"[{code}] ",
        )
        scoped["by_service"][code] = {
            "total": cohort.count(),
            "new": cohort.filter(status="new").count(),
            "reviewing": cohort.filter(status="reviewing").count(),
            "internal_draft_prepared": cohort.filter(
                internal_note__contains=DRAFT_MARKER
            ).count(),
        }
    preview = preview_candidates(limit=20)
    scoped["candidate_scan"] = {
        "inspected": preview["candidate_count"],
        "eligible": preview["eligible_count"],
        "requires_human_review": preview["requires_human_review_count"],
        "review_reasons": preview["review_reason_counts"],
        "scan_complete": preview["scan_complete"],
        "scan_limit_reached": preview["scan_limit_reached"],
        "max_records": preview["scan_rows_max"],
    }
    return scoped



@user_passes_test(
    lambda user: bool(user.is_active and user.is_superuser),
    login_url="/admin/login/",
)
@require_GET
def service_proposal_funnel_dashboard(request):
    """A real owner workbench; counts link to the existing protected CRM."""
    from django.urls import reverse

    snapshot = service_proposal_funnel_snapshot()
    total = snapshot["total_consent_provenance"]
    prepared = snapshot["draft_prepared_total"]
    snapshot["preparation_percentage"] = (
        round(100 * prepared / total, 2) if total else None
    )
    response = render(
        request,
        "command_center/service_proposal_funnel.html",
        {
            "funnel": snapshot,
            "admin_leads_url": reverse("admin:core_companyinquiry_changelist"),
        },
    )
    response["Cache-Control"] = "no-store, private, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Vary"] = "Cookie"
    return response


@user_passes_test(
    lambda user: bool(user.is_active and user.is_superuser),
    login_url="/admin/login/",
)
@require_GET
def service_proposal_funnel_api(request):
    response = JsonResponse(service_proposal_funnel_snapshot())
    response["Cache-Control"] = "no-store, private, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Vary"] = "Cookie"
    return response
