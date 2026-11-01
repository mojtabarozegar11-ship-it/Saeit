"""Read-only, permission-scoped management project register.

This page displays recorded data only. It does not approve projects, post
financial entries, infer profitability, or contact external services.
"""
from django.db import transaction
from django.db.models import F, Sum
from django.forms import ModelForm, DateInput
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from ecosystem_hub.access import require_unit, user_units
from .models import AuditEvent, BudgetPlan, ManagementProject
from .views import office_access, page, required_permission


class ProjectForm(ModelForm):
    class Meta:
        model = ManagementProject
        fields = ("unit", "code", "title", "objective", "planned_start", "planned_finish")
        widgets = {
            "planned_start": DateInput(attrs={"type": "date"}),
            "planned_finish": DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unit"].queryset = user_units(user).filter(active=True)


@never_cache
@office_access
@csrf_protect
@require_http_methods(["GET", "POST"])
def new_project(request):
    """Create only an idea-stage project; approvals and spending are separate."""
    required_permission(request, "add_managementproject")
    form = ProjectForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        require_unit(request.user, project.unit, write=True)
        project.owner = request.user
        project.status = "idea"
        with transaction.atomic():
            project.full_clean()
            project.save()
            AuditEvent.objects.create(
                actor=request.user, action="office_project_created",
                target=f"ManagementProject:{project.pk}",
                detail={"unit_id": project.unit_id, "code": project.code,
                        "status": "idea", "no_external_side_effects": True},
            )
        return redirect("enterprise_portal:project_detail", pk=project.pk)
    return page(request, "form", {
        "section": "projects", "form": form, "heading": "ثبت ایده یا پروژه جدید",
        "submit_label": "ثبت پرونده در مرحله مطالعه",
        "back_url": "/company/office/projects/",
    })


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
        "can_add": request.user.is_superuser or request.user.has_perm("enterprise_portal.add_managementproject"),
    })
