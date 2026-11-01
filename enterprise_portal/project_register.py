"""Read-only, permission-scoped management project register.

This page displays recorded data only. It does not approve projects, post
financial entries, infer profitability, or contact external services.
"""
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from ecosystem_hub.access import user_units
from .models import BudgetPlan, ManagementProject
from .views import office_access, page, required_permission


@never_cache
@office_access
@require_GET
def project_register(request, pk=None):
    required_permission(request, "view_managementproject")
    units = user_units(request.user)
    visible = ManagementProject.objects.select_related("unit", "owner").filter(
        unit__in=units
    )
    if pk is not None:
        project = get_object_or_404(visible, pk=pk)
        budgets = BudgetPlan.objects.filter(
            project=project, unit=project.unit
        ).order_by("currency", "fiscal_year", "pk")
        return page(request, "project_register", {
            "section": "projects", "item": project, "budgets": budgets,
        })

    projects = list(visible.order_by("unit__code", "code", "pk")[:150])
    by_id = {project.pk: project for project in projects}
    if by_id:
        totals = BudgetPlan.objects.filter(
            project_id__in=by_id,
            unit_id=F("project__unit_id"),
            status="approved",
        ).values("project_id", "currency").annotate(total=Sum("amount"))
        for project in projects:
            project.approved_budgets = []
        for row in totals:
            by_id[row["project_id"]].approved_budgets.append({
                "currency": row["currency"], "total": row["total"],
            })
    return page(request, "project_register", {
        "section": "projects", "projects": projects, "record_limit": 150,
    })
