from django.contrib import admin

from .models import CommerceBuyerIdentity


@admin.register(CommerceBuyerIdentity)
class CommerceBuyerIdentityAdmin(admin.ModelAdmin):
    """Read-only staff view; identity data is never editable from admin."""
    list_display = (
        "order_id", "email_address", "network", "payer_wallet",
        "tx_hash", "source", "verified_at",
    )
    search_fields = ("email_address", "payer_wallet", "tx_hash", "order__id")
    readonly_fields = (
        "order", "email_address", "email_digest", "payer_wallet",
        "network", "tx_hash", "source", "verified_at",
        "created_at", "updated_at",
    )
    list_select_related = ("order",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
