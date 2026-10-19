"""Host-scoped internal production admin; no customer checkout or factory dispatch."""
from django.contrib import admin
from django.contrib.admin import ModelAdmin

from .mojplaywin_production_models import (
    MojPlayWinManufacturingOrder,
    MojPlayWinOpportunitySignal,
)


class _MojPlayWinMainOnlyAdmin(ModelAdmin):
    """Do not show or operate these records on Zomorod or any sub-site host."""

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
        "proposal_id", "product_title", "source_card", "priority_hypothesis",
        "status", "proposed_owner", "demand_verified", "rights_verified",
    )
    list_filter = ("status", "priority_hypothesis", "demand_verified", "rights_verified")
    search_fields = ("proposal_id", "product_title", "signal__card_title", "review_note")
    list_select_related = ("signal", "proposed_owner")
    ordering = ("-priority_hypothesis", "proposal_id")
    fields = (
        "proposal_id", "source_card", "product_title", "file_format", "deliverable",
        "priority_hypothesis", "status", "proposed_owner", "review_note",
        "demand_verified", "rights_verified", "created_at", "updated_at",
    )
    readonly_fields = (
        "proposal_id", "source_card", "product_title", "file_format", "deliverable",
        "priority_hypothesis", "demand_verified", "rights_verified",
        "created_at", "updated_at",
    )

    @admin.display(description="Origin card")
    def source_card(self, obj):
        return "%s — %s" % (obj.signal.source_key, obj.signal.card_title)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(signal__source_site=MojPlayWinOpportunitySignal.SITE)
