"""Strictly read-only operator inspection; no manual financial history fabrication."""
from django.contrib import admin
from .models import (
    PropTrader, PropAccount, PropExecution, PropEquityObservation, PropDecisionLog,
    PropProfitAllocation, PropProfitJournalLine, PropSocialEvidence, PropChallengeEnrollment,
    PropInformationInquiry,
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
    list_display = ("id", "account_id", "symbol", "external_position_id",
                    "execution_origin", "reconciliation_status", "closed_at")
    list_filter = ("reconciliation_status",)


@admin.register(PropEquityObservation)
class PropEquityAdmin(LockedAuditAdmin):
    list_display = ("id", "account_id", "equity_usd", "reconciliation_status", "observed_at")


@admin.register(PropDecisionLog)
class PropDecisionAdmin(LockedAuditAdmin):
    list_display = ("id", "account_id", "category", "qualifies", "policy_version", "recorded_at")



@admin.register(PropProfitAllocation)
class PropProfitAllocationAdmin(LockedAuditAdmin):
    """Inspectable draft allocations; no approval or payout actions."""
    list_display = (
        "id", "account_id", "period_number", "eligible_profit_usd",
        "trader_profit_usd", "company_profit_usd", "status",
    )
    list_filter = ("status", "policy_version")


@admin.register(PropProfitJournalLine)
class PropProfitJournalAdmin(LockedAuditAdmin):
    """Inspect three-sided internal memo journal; never an accounts-payable UI."""
    list_display = ("id", "allocation_id", "code", "side", "amount_usd")
    list_filter = ("code", "side")



@admin.register(PropSocialEvidence)
class PropSocialEvidenceAdmin(LockedAuditAdmin):
    """Operator review history; social posting and modifications are not enabled."""
    list_display = (
        "enrollment_id", "account_id", "platform", "review_status",
        "author_verified", "disclosure_verified",
        "continued_visibility_verified", "posted_at", "reviewed_at",
    )
    list_filter = ("platform", "review_status", "disclosure_verified")


@admin.register(PropChallengeEnrollment)
class PropChallengeEnrollmentAdmin(LockedAuditAdmin):
    """Read-only confirmed purchase, shared by both stages; never issue an invoice."""
    list_display = (
        "id", "trader_id", "plan_code", "confirmed_at",
        "settlement_verified", "terms_version",
    )
    list_filter = ("settlement_verified", "terms_version")

@admin.register(PropInformationInquiry)
class PropInformationInquiryAdmin(LockedAuditAdmin):
    """Owner-only read; no sending, export action, mutation or deletion."""
    list_display = ("id", "email", "status", "consent_version", "created_at", "expires_at")
    list_filter = ("status", "consent_version")
    search_fields = ("email",)
    readonly_fields = ("email", "email_digest", "status", "consent_version", "created_at", "expires_at")

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_authenticated and request.user.is_superuser)

    def has_module_permission(self, request):
        return bool(request.user.is_authenticated and request.user.is_superuser)
