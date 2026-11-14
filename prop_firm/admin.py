"""Strictly read-only operator inspection; no manual financial history fabrication."""
from django.contrib import admin
from .models import (
    PropTrader, PropAccount, PropExecution, PropEquityObservation, PropDecisionLog,
)


class LockedAuditAdmin(admin.ModelAdmin):
    actions = None
    list_per_page = 30

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PropTrader)
class PropTraderAdmin(LockedAuditAdmin):
    list_display = ("id", "user_id", "preferred_language", "kyc_status", "eligibility_status")


@admin.register(PropAccount)
class PropAccountAdmin(LockedAuditAdmin):
    list_display = ("id", "trader_id", "kind", "status", "starting_capital_usd", "policy_version")
    list_filter = ("kind", "status")


@admin.register(PropExecution)
class PropExecutionAdmin(LockedAuditAdmin):
    list_display = ("id", "account_id", "symbol", "reconciliation_status", "closed_at")
    list_filter = ("reconciliation_status",)


@admin.register(PropEquityObservation)
class PropEquityAdmin(LockedAuditAdmin):
    list_display = ("id", "account_id", "equity_usd", "reconciliation_status", "observed_at")


@admin.register(PropDecisionLog)
class PropDecisionAdmin(LockedAuditAdmin):
    list_display = ("id", "account_id", "category", "qualifies", "policy_version", "recorded_at")
