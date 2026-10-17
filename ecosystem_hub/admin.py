"""Restrict change-list, direct-object and reference lookups by accessible unit."""
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.db.models import Q
from enterprise_portal.models import (
    BusinessUnit, InventoryItem, CompanyAsset, ManagementProject,
)
from .access import user_units, can_view_unit, require_unit
from .models import (
    Organization, UnitMembership, ManagedSite, WorkCenter, BillOfMaterials,
    MaterialRequirement, ProductionOrder, ProcurementNeed, QualityInspection,
    MaintenanceTicket, StaffAssignment, Timesheet, ManagementRisk,
    PerformanceIndicator, ReviewApproval, ReferenceEvidence, AssistantRun,
    ProposedAutomation, MaterialPriceReference, ProductionCostScenario,
)


class ScopedAdmin(admin.ModelAdmin):
    unit_lookup = "unit"
    list_per_page = 40

    def _unit(self, obj):
        if not obj:
            return None
        if isinstance(obj, MaterialRequirement):
            return obj.formula.unit
        return getattr(obj, "unit", None)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(**{self.unit_lookup + "__in": user_units(request.user)})

    def has_view_permission(self, request, obj=None):
        if obj is not None and not can_view_unit(request.user, self._unit(obj)):
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            try:
                require_unit(request.user, self._unit(obj), write=True)
            except PermissionDenied:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Never expose unsafe Django bulk deletions to scoped staff.
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "unit":
            kwargs["queryset"] = user_units(request.user)
        elif db_field.related_model in (InventoryItem, CompanyAsset, ManagementProject):
            kwargs["queryset"] = db_field.related_model.objects.filter(unit__in=user_units(request.user))
        elif db_field.related_model in (BillOfMaterials, WorkCenter, ProductionOrder):
            kwargs["queryset"] = db_field.related_model.objects.filter(unit__in=user_units(request.user))
        elif db_field.related_model is Organization:
            kwargs["queryset"] = Organization.objects.filter(unit__in=user_units(request.user))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        unit = self._unit(obj)
        if unit:
            require_unit(request.user, unit, write=True)
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(Organization)
class OrganizationAdmin(ScopedAdmin):
    list_display = ("legal_name", "unit", "is_legal_entity", "parent", "default_currency")
    list_filter = ("is_legal_entity",)
    search_fields = ("legal_name", "unit__name")


@admin.register(UnitMembership)
class UnitMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "unit", "role", "can_approve", "active")
    list_filter = ("unit", "role", "active")
    search_fields = ("user__username", "unit__name")

    def get_queryset(self, request):
        # Assignment of cross-unit permissions is exclusively an owner action.
        return super().get_queryset(request) if request.user.is_superuser else super().get_queryset(request).none()

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ManagedSite)
class ManagedSiteAdmin(ScopedAdmin):
    list_display = ("label", "unit", "path", "status", "last_reviewed_at")
    search_fields = ("label", "path")


@admin.register(WorkCenter)
class WorkCenterAdmin(ScopedAdmin):
    list_display = ("code", "name", "unit", "nominal_hours_per_day", "active")
    list_filter = ("unit", "active")


class MaterialInline(admin.TabularInline):
    model = MaterialRequirement
    extra = 0

    def has_delete_permission(self, request, obj=None):
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "item":
            kwargs["queryset"] = InventoryItem.objects.filter(unit__in=user_units(request.user))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(BillOfMaterials)
class BillOfMaterialsAdmin(ScopedAdmin):
    list_display = ("code", "revision", "product", "unit", "yield_quantity", "state")
    list_filter = ("unit", "state")
    inlines = (MaterialInline,)


@admin.register(MaterialRequirement)
class MaterialRequirementAdmin(ScopedAdmin):
    unit_lookup = "formula__unit"
    list_display = ("formula", "item", "quantity", "scrap_percent")
    list_select_related = ("formula", "item")

    def has_add_permission(self, request):
        return False  # Add BOM components through scoped parent inline only.


@admin.register(ProductionOrder)
class ProductionOrderAdmin(ScopedAdmin):
    list_display = ("code", "unit", "formula", "quantity", "work_center", "due_date", "state")
    list_filter = ("unit", "state")
    search_fields = ("code",)


@admin.register(MaterialPriceReference)
class MaterialPriceReferenceAdmin(ScopedAdmin):
    list_display = ("item", "unit", "currency", "amount", "as_of", "status", "evidence_ref")

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.status == "verified":
            return False
        return super().has_change_permission(request, obj)
    list_filter = ("unit", "currency", "status")
    search_fields = ("item__sku", "item__title", "evidence_ref")
    readonly_fields = ("recorded_by", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ProductionCostScenario)
class ProductionCostScenarioAdmin(ScopedAdmin):
    list_display = ("label", "unit", "order", "currency", "labor_estimate", "overhead_estimate")
    list_filter = ("unit", "currency")
    search_fields = ("label", "order__code")
    readonly_fields = ("prepared_by", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.prepared_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ProcurementNeed)
class ProcurementNeedAdmin(ScopedAdmin):
    list_display = ("reference", "unit", "item", "quantity", "required_by", "status")
    list_filter = ("unit", "status")


@admin.register(QualityInspection)
class QualityInspectionAdmin(ScopedAdmin):
    list_display = ("title", "unit", "order", "sample_ref", "result", "inspected_on")
    list_filter = ("unit", "result")


@admin.register(MaintenanceTicket)
class MaintenanceTicketAdmin(ScopedAdmin):
    list_display = ("title", "unit", "asset", "priority", "due_date", "status")
    list_filter = ("unit", "priority", "status")


@admin.register(StaffAssignment)
class StaffAssignmentAdmin(ScopedAdmin):
    list_display = ("person", "unit", "title", "active")


@admin.register(Timesheet)
class TimesheetAdmin(ScopedAdmin):
    list_display = ("person", "unit", "work_date", "hours", "approved")


@admin.register(ManagementRisk)
class ManagementRiskAdmin(ScopedAdmin):
    list_display = ("title", "unit", "owner", "likelihood", "impact", "state")
    list_filter = ("unit", "state")


@admin.register(PerformanceIndicator)
class PerformanceIndicatorAdmin(ScopedAdmin):
    list_display = ("code", "label", "unit", "period", "target", "actual")
    list_filter = ("unit", "period")


@admin.register(ReviewApproval)
class ReviewApprovalAdmin(ScopedAdmin):
    list_display = ("summary", "unit", "assigned_to", "decision", "reviewed_at")
    list_filter = ("unit", "decision")
    readonly_fields = ("reviewed_at",)

    def save_model(self, request, obj, form, change):
        if change:
            original = ReviewApproval.objects.get(pk=obj.pk)
            immutable = ("unit_id", "summary", "target_type", "target_reference",
                         "requested_by_id", "assigned_to_id")
            if any(getattr(original, name) != getattr(obj, name) for name in immutable):
                raise ValidationError("شناسه و دامنه درخواست تصمیم پس از ثبت قابل تغییر نیست.")
            if original.decision != "pending":
                raise ValidationError("تصمیم ثبت‌شده قابل تغییر نیست؛ پرونده جدید تشکیل دهید.")
            if obj.decision != "pending":
                require_unit(request.user, obj.unit, approve=True)
                if not request.user.is_superuser and original.assigned_to_id != request.user.pk:
                    raise PermissionDenied("این درخواست به شما ارجاع نشده است.")
                obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(ReferenceEvidence)
class ReferenceEvidenceAdmin(ScopedAdmin):
    list_display = ("title", "unit", "document_ref", "reviewed")
    list_filter = ("unit", "reviewed")


@admin.register(AssistantRun)
class AssistantRunAdmin(ScopedAdmin):
    list_display = ("assistant_code", "unit", "requested_by", "generated_at", "state")
    readonly_fields = ("unit", "assistant_code", "requested_by", "generated_at", "findings", "evidence", "state", "reviewed_by")

    def has_add_permission(self, request):
        return False  # Executions go through authenticated, scoped, audited services.

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ProposedAutomation)
class ProposedAutomationAdmin(ScopedAdmin):
    list_display = ("assistant_code", "unit", "cadence", "active", "requires_human_review", "last_checked_at")

    def save_model(self, request, obj, form, change):
        obj.requires_human_review = True
        super().save_model(request, obj, form, change)
