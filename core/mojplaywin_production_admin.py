"""Host-scoped four-origin manufacturing review; QA history is not deletable."""
from uuid import uuid4

from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.db.models import Q

from .mojplaywin_production_models import (
    MojPlayWinManufacturingOrder,
    MojPlayWinOpportunitySignal,
    MojPlayWinQAReview,
    MojPlayWinQADefect,
    MojPlayWinReworkCycle,
)


class _MojPlayWinMainOnlyAdmin(ModelAdmin):
    """No main-site production records on Zomorod or sub-site admin hosts."""

    @staticmethod
    def _allowed(request):
        host = request.get_host().split(":", 1)[0].lower()
        return (
            host in ("mojplaywin.com", "www.mojplaywin.com")
            and request.user.is_active
            and request.user.is_superuser
        )

    def has_module_permission(self, request):
        return self._allowed(request) and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return self._allowed(request) and super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._allowed(request) and super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MojPlayWinOpportunitySignal)
class MojPlayWinOpportunitySignalAdmin(_MojPlayWinMainOnlyAdmin):
    list_display = ("source_key", "source_kind", "card_title", "source_site", "created_at")
    list_filter = ("source_kind",)
    search_fields = ("source_key", "card_title", "card_description")
    ordering = ("source_key",)
    fields = (
        "source_key", "source_site", "source_kind", "source_path",
        "card_title", "card_description", "review_note", "created_at",
    )
    readonly_fields = (
        "source_key", "source_site", "source_kind", "source_path",
        "card_title", "card_description", "created_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(source_site=MojPlayWinOpportunitySignal.SITE)


@admin.register(MojPlayWinManufacturingOrder)
class MojPlayWinManufacturingOrderAdmin(_MojPlayWinMainOnlyAdmin):
    list_display = (
        "proposal_id", "origin_type", "product_title", "source_card", "priority_hypothesis",
        "status", "production_stage", "quality_round", "proposed_owner",
        "demand_verified", "rights_verified",
    )
    list_filter = (
        "origin_type", "status", "production_stage", "priority_hypothesis",
        "demand_verified", "rights_verified",
    )
    search_fields = (
        "proposal_id", "origin_reference", "origin_description",
        "product_title", "signal__card_title", "review_note",
    )
    list_select_related = ("signal", "proposed_owner")
    ordering = ("-priority_hypothesis", "proposal_id")
    fields = (
        "proposal_id", "origin_type", "origin_reference", "origin_description",
        "source_card", "product_title", "file_format", "deliverable",
        "priority_hypothesis", "status", "production_stage", "quality_round",
        "proposed_owner", "review_note",
        "demand_verified", "rights_verified", "created_at", "updated_at",
    )
    readonly_fields = (
        "proposal_id", "origin_type", "origin_reference", "origin_description",
        "source_card", "product_title", "file_format", "deliverable",
        "priority_hypothesis", "production_stage", "quality_round",
        "demand_verified", "rights_verified", "created_at", "updated_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            Q(origin_type="site", signal__source_site=MojPlayWinOpportunitySignal.SITE)
            | Q(origin_type__in=("customer", "market", "invention"), signal__isnull=True)
        )

    @admin.display(description="Origin")
    def source_card(self, obj):
        if not obj:
            return "Independent production request"
        if obj.signal_id:
            return "%s — %s" % (obj.signal.source_key, obj.signal.card_title)
        return obj.origin_reference or obj.get_origin_type_display()

    def has_add_permission(self, request):
        return self._allowed(request) and super(_MojPlayWinMainOnlyAdmin, self).has_add_permission(request)

    def get_fields(self, request, obj=None):
        if obj is None:
            return (
                "origin_type", "origin_reference", "origin_description",
                "product_title", "file_format", "deliverable",
                "priority_hypothesis", "proposed_owner", "review_note",
            )
        return super().get_fields(request, obj)

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else super().get_readonly_fields(request, obj)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "origin_type":
            kwargs["choices"] = [
                choice for choice in MojPlayWinManufacturingOrder.ORDER_ORIGINS
                if choice[0] in ("customer", "market", "invention")
            ]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            if obj.origin_type not in ("customer", "market", "invention") or obj.signal_id:
                raise ValueError("Only non-site independent production requests may be added manually")
            obj.proposal_id = "MPW-MAN-" + uuid4().hex[:20].upper()
            if obj.proposed_owner_id is None:
                obj.proposed_owner = request.user
            obj.status = "proposed_for_review"
            obj.production_stage = "not_started"
        obj.full_clean()
        super().save_model(request, obj, form, change)


class _ReadOnlyQualityAdmin(_MojPlayWinMainOnlyAdmin):
    """QA inspectors use the auditable service, never an inline bypass."""
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MojPlayWinQAReview)
class MojPlayWinQAReviewAdmin(_ReadOnlyQualityAdmin):
    list_display = ("review_key", "brief", "round_number", "verdict", "reviewed_by", "created_at")
    list_filter = ("verdict", "round_number", "created_at")
    search_fields = ("review_key", "brief__product_title", "summary", "artifact_reference")
    list_select_related = ("brief", "reviewed_by")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            Q(brief__origin_type="site", brief__signal__source_site="mojplaywin.com")
            | Q(brief__origin_type__in=("customer", "market", "invention"), brief__signal__isnull=True)
        )


@admin.register(MojPlayWinQADefect)
class MojPlayWinQADefectAdmin(_ReadOnlyQualityAdmin):
    list_display = (
        "defect_code", "review", "severity", "cause", "correction_plan",
        "resolved_at", "resolved_by",
    )
    list_filter = ("severity", "resolved_at")
    search_fields = ("defect_code", "cause", "actual", "expected", "correction_plan", "resolution_evidence")
    list_select_related = ("review", "resolved_by")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            Q(review__brief__origin_type="site", review__brief__signal__source_site="mojplaywin.com")
            | Q(review__brief__origin_type__in=("customer", "market", "invention"), review__brief__signal__isnull=True)
        )


@admin.register(MojPlayWinReworkCycle)
class MojPlayWinReworkCycleAdmin(_ReadOnlyQualityAdmin):
    list_display = ("brief", "failed_review", "attempt_number", "state", "instructions", "created_at")
    list_filter = ("state", "attempt_number", "created_at")
    search_fields = ("brief__product_title", "failed_review__review_key", "instructions", "fix_summary")
    list_select_related = ("brief", "failed_review")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            Q(brief__origin_type="site", brief__signal__source_site="mojplaywin.com")
            | Q(brief__origin_type__in=("customer", "market", "invention"), brief__signal__isnull=True)
        )
