"""Native Django administration: per-model permissions, inlines and safe actions."""
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import (
    AuditEvent, BudgetPlan, BusinessUnit, CommercialDocument, CompanyAsset,
    InventoryItem, JournalEntry, JournalLine, LedgerAccount, ManagementProject,
    Meeting, OfficeLetter, Partner, StockMovement, WorkTask,
)
from .services import confirm_stock_movement, post_journal


class OwnedByAdmin(admin.ModelAdmin):
    """Populate audit attribution from the authenticated staff session."""
    creator_field = "created_by"

    def save_model(self, request, obj, form, change):
        if not change and not getattr(obj, f"{self.creator_field}_id", None):
            setattr(obj, self.creator_field, request.user)
        super().save_model(request, obj, form, change)


@admin.register(BusinessUnit)
class BusinessUnitAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "sector", "active")
    list_filter = ("sector", "active")
    search_fields = ("name", "code")


@admin.register(LedgerAccount)
class LedgerAccountAdmin(admin.ModelAdmin):
    list_display = ("unit", "code", "name", "category", "active")
    list_filter = ("unit", "category", "active")
    search_fields = ("code", "name")


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 2
    autocomplete_fields = ("account",)

    def has_add_permission(self, request, obj=None):
        return bool(obj and obj.status == "draft") and super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return bool(obj and obj.status == "draft") and super().has_delete_permission(request, obj)


@admin.register(JournalEntry)
class JournalEntryAdmin(OwnedByAdmin):
    list_display = ("reference", "unit", "booked_on", "currency", "status", "posted_at")
    list_filter = ("unit", "currency", "status")
    search_fields = ("reference", "description")
    readonly_fields = ("status", "posted_at", "created_by", "created_at", "updated_at")
    inlines = (JournalLineInline,)
    actions = ("post_selected",)
    list_select_related = ("unit",)

    def has_change_permission(self, request, obj=None):
        return (obj is None or obj.status == "draft") and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return (obj is None or obj.status == "draft") and super().has_delete_permission(request, obj)

    @admin.action(description="قطعی‌سازی اسناد متوازن انتخاب‌شده")
    def post_selected(self, request, queryset):
        if not request.user.has_perm("enterprise_portal.change_journalentry"):
            self.message_user(request, "مجوز قطعی‌سازی ندارید.", level=messages.ERROR)
            return
        ok = 0
        for obj in queryset.order_by("pk"):
            try:
                post_journal(obj.pk, request.user)
            except ValidationError as exc:
                self.message_user(request, f"سند {obj.reference}: {exc}", level=messages.ERROR)
            else:
                ok += 1
        if ok:
            self.message_user(request, f"{ok} سند متوازن، پس از کنترل بدهکار/بستانکار، قطعی شد.")


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "kind", "contact")
    list_filter = ("unit", "kind")
    search_fields = ("name", "tax_id", "email")


@admin.register(CommercialDocument)
class CommercialDocumentAdmin(OwnedByAdmin):
    list_display = ("number", "unit", "partner", "kind", "total", "currency", "status", "due_on")
    list_filter = ("kind", "currency", "status", "unit")
    search_fields = ("number", "partner__name")
    readonly_fields = ("created_by", "created_at", "updated_at")
    autocomplete_fields = ("partner",)

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "title", "unit", "measure", "reorder_point", "active")
    list_filter = ("unit", "active")
    search_fields = ("sku", "title")


@admin.register(StockMovement)
class StockMovementAdmin(OwnedByAdmin):
    list_display = ("reference", "item", "direction", "quantity", "status", "confirmed_at")
    list_filter = ("status", "direction", "item__unit")
    search_fields = ("reference", "item__sku")
    readonly_fields = ("status", "confirmed_at", "created_by", "created_at", "updated_at")
    actions = ("confirm_selected",)
    autocomplete_fields = ("item",)

    def has_change_permission(self, request, obj=None):
        return (obj is None or obj.status == "draft") and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return (obj is None or obj.status == "draft") and super().has_delete_permission(request, obj)

    @admin.action(description="تأیید گردش انبار با کنترل موجودی")
    def confirm_selected(self, request, queryset):
        if not request.user.has_perm("enterprise_portal.change_stockmovement"):
            self.message_user(request, "دسترسی تأیید انبار ندارید.", level=messages.ERROR)
            return
        count = 0
        for obj in queryset.order_by("pk"):
            try:
                confirm_stock_movement(obj.pk, request.user)
            except ValidationError as exc:
                self.message_user(request, f"{obj.reference}: {exc}", level=messages.ERROR)
            else:
                count += 1
        if count:
            self.message_user(request, f"{count} گردش انبار با موفقیت قطعی شد.")


@admin.register(OfficeLetter)
class OfficeLetterAdmin(OwnedByAdmin):
    list_display = ("number", "subject", "direction", "classification", "assigned_to", "sent_on")
    list_filter = ("direction", "classification", "sent_on")
    search_fields = ("number", "subject")
    readonly_fields = ("created_by", "created_at", "updated_at")

    def _may_read_secret(self, user, obj):
        return bool(user.is_superuser or
                    user.has_perm("enterprise_portal.view_confidential_letters") or
                    (obj and (obj.created_by_id == user.pk or obj.assigned_to_id == user.pk)))

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.has_perm("enterprise_portal.view_confidential_letters"):
            return qs
        return qs.filter(Q(classification="normal") | Q(created_by=request.user) |
                         Q(assigned_to=request.user))

    def has_view_permission(self, request, obj=None):
        if obj and obj.classification == "confidential" and not self._may_read_secret(request.user, obj):
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj and obj.classification == "confidential" and not self._may_read_secret(request.user, obj):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.classification == "confidential" and not self._may_read_secret(request.user, obj):
            return False
        return super().has_delete_permission(request, obj)


@admin.register(WorkTask)
class WorkTaskAdmin(OwnedByAdmin):
    list_display = ("title", "unit", "assigned_to", "priority", "status", "due_on")
    list_filter = ("priority", "status", "unit")
    search_fields = ("title", "description")
    readonly_fields = ("created_by", "created_at", "updated_at")
    autocomplete_fields = ("assigned_to",) if False else ()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.has_perm("enterprise_portal.change_worktask"):
            return qs
        return qs.filter(Q(assigned_to=request.user) | Q(created_by=request.user))


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("title", "starts_at", "ends_at", "organizer", "location")
    search_fields = ("title", "location", "agenda")
    filter_horizontal = ("attendees",)

    def save_model(self, request, obj, form, change):
        if not change and not obj.organizer_id:
            obj.organizer = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(ManagementProject)
class ManagementProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "unit", "owner", "status", "planned_finish")
    list_filter = ("status", "unit")
    search_fields = ("title", "code")

    def save_model(self, request, obj, form, change):
        if not change and not obj.owner_id:
            obj.owner = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(BudgetPlan)
class BudgetPlanAdmin(admin.ModelAdmin):
    list_display = ("title", "unit", "project", "fiscal_year", "amount", "currency", "status")
    list_filter = ("fiscal_year", "unit", "status", "currency")
    search_fields = ("title",)

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(CompanyAsset)
class CompanyAssetAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "unit", "acquired_on", "purchase_cost", "currency", "custodian")
    list_filter = ("unit", "currency")
    search_fields = ("code", "title")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "actor", "action", "target")
    list_filter = ("action", "occurred_at")
    search_fields = ("target", "actor__username")
    readonly_fields = ("occurred_at", "actor", "action", "target", "detail")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
