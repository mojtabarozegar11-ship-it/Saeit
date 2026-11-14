"""Owner-only actionable queue over existing CompanyInquiry records.

The queue returns IDs and internal admin paths, not PII. A review/approved
stage must never be interpreted as a signed service agreement or settled cash.
"""
from __future__ import annotations

import re
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.company_inquiry_models import CompanyInquiry
from core.service_sales_controls import SERVICE_CARDS

PAGE_SIZE = 25
MAX_PAGE = 100
_STATUSES = frozenset({"all", "new", "reviewing", "approved"})
_KINDS = frozenset({"all", *(c for c, _ in CompanyInquiry.KIND_CHOICES)})
_CODE_PATTERN = re.compile(
    r"^\[(" + "|".join(re.escape(code) for code in SERVICE_CARDS) + r")\] "
)


def _priority(status, age_days):
    if age_days >= 30:
        return "overdue_30d"
    if age_days >= 7:
        return "overdue_7d"
    if status == "new":
        return "first_review"
    return "follow_up"


def lead_workqueue_snapshot(*, status="all", kind="all", page=1, now=None):
    if status not in _STATUSES or kind not in _KINDS:
        raise ValueError("unsupported status or kind")
    if type(page) is not int or not 1 <= page <= MAX_PAGE:
        raise ValueError("page out of range")
    end = now or timezone.now()
    queryset = CompanyInquiry.objects.exclude(status="closed").filter(
        created_at__lte=end
    )
    if status != "all":
        queryset = queryset.filter(status=status)
    if kind != "all":
        queryset = queryset.filter(kind=kind)
    total = queryset.count()
    start = (page - 1) * PAGE_SIZE
    selected = list(
        queryset.order_by("created_at", "pk")
        .values("pk", "status", "kind", "created_at", "subject")[start:start + PAGE_SIZE + 1]
    )
    has_more = len(selected) > PAGE_SIZE
    entries = []
    for item in selected[:PAGE_SIZE]:
        age = max(0, (end - item["created_at"]).days)
        match = _CODE_PATTERN.match(item["subject"] or "")
        entries.append({
            "inquiry_id": item["pk"],
            "status": item["status"],
            "kind": item["kind"],
            "service_code": match.group(1) if match else None,
            "age_days": age,
            "priority": _priority(item["status"], age),
            "created_at": item["created_at"].isoformat(),
            "admin_detail_path": reverse(
                "admin:core_companyinquiry_change", args=[item["pk"]]
            ),
        })
    return {
        "agent": "mojtaba.bot.ai",
        "schema_version": 1,
        "read_only": True,
        "owner_only": True,
        "customer_pii_in_response": False,
        "status_filter": status,
        "kind_filter": kind,
        "page": page,
        "page_size": PAGE_SIZE,
        "matching_open_requests": total,
        "has_more": has_more,
        "items": entries,
        "stage_approved_means": "preliminary_review_not_signed_contract",
        "settled_cash": None,
        "delivery_evidence": None,
    }


@user_passes_test(
    lambda user: bool(user.is_active and user.is_superuser),
    login_url="/admin/login/",
)
@require_GET
def lead_workqueue_api(request):
    """Controlled GET API; dynamic admin detail paths require separate auth."""
    status = request.GET.get("status", "all")
    kind = request.GET.get("kind", "all")
    page = request.GET.get("page", "1")
    try:
        if not re.fullmatch(r"[1-9][0-9]{0,2}", page):
            raise ValueError("page must be canonical positive integer")
        snapshot = lead_workqueue_snapshot(
            status=status, kind=kind, page=int(page)
        )
    except (ValueError, TypeError):
        response = JsonResponse({"error": "invalid queue filters"}, status=400)
    else:
        response = JsonResponse(snapshot)
    response["Cache-Control"] = "no-store, private, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Vary"] = "Cookie"
    return response
