"""Read-only identities and controlled follow-up for Mojtaba.bot.ai leads."""
from django.contrib import admin
from .signal_interest_models import CommercialInterest


@admin.register(CommercialInterest)
class CommercialInterestAdmin(admin.ModelAdmin):
    list_per_page = 30
    actions = None
    list_display = ("id", "email", "offer_family", "brand", "plan_code", "status",
                    "source_language", "created_at", "withdrawn_at")
    list_filter = ("status", "offer_family", "brand", "plan_code", "source_language")
    search_fields = ("email",)
    fields = ("email", "offer_family", "brand", "plan_code", "consent_version",
              "source_language", "source_host", "status",
              "created_at", "updated_at", "withdrawn_at")
    readonly_fields = ("email", "offer_family", "brand", "plan_code", "consent_version",
                       "source_language", "source_host", "created_at", "updated_at", "withdrawn_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def _owner(self, request):
        user = getattr(request, "user", None)
        return bool(user and getattr(user, "is_active", False)
                    and getattr(user, "is_superuser", False))

    def has_view_permission(self, request, obj=None):
        return self._owner(request) and super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._owner(request) and super().has_change_permission(request, obj)
