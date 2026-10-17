"""Native Django administration: per-model permissions, inlines and safe actions."""
from django.contrib import admin, messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Q
from .models import (
    AuditEvent, BudgetPlan, BusinessUnit, CommercialDocument, CompanyAsset,
    InventoryItem, JournalEntry, JournalLine, LedgerAccount, ManagementProject,
    Meeting, OfficeLetter, Partner, StockMovement, WorkTask,
)
from .services import confirm_stock_movement, post_journal
from ecosystem_hub.access import can_view_unit, require_unit, user_units



class UnitScopedERPAdmin(admin.ModelAdmin):
    """Scope *all* finance and warehouse Django-admin records to unit membership.

    A Django model-level permission is necessary, never sufficient, for seeing
    another company's vouchers, vendor records, SKUs or financial assets.
    """
    unit_path = "unit"

    def _unit(self, obj):
        if not obj:
            return None
        if isinstance(obj, BusinessUnit):
            return obj
        if isinstance(obj, StockMovement):
            return obj.item.unit
        return obj.unit

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            **{self.unit_path + "__in": user_units(request.user)}
        )

    def has_view_permission(self, request, obj=None):
        if obj and not can_view_unit(request.user, self._unit(obj)):
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            try:
                require_unit(request.user, self._unit(obj), write=True)
            except PermissionDenied:
                return False
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        return super().has_add_permission(request) and user_units(request.user).exists()

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        allowed = user_units(request.user)
        if db_field.name == "unit":
            kwargs["queryset"] = allowed
        elif db_field.related_model in (Partner, InventoryItem, LedgerAccount, ManagementProject):
            kwargs["queryset"] = db_field.related_model.objects.filter(unit__in=allowed)
        elif db_field.related_model is JournalEntry:
            kwargs["queryset"] = JournalEntry.objects.filter(unit__in=allowed)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        require_unit(request.user, self._unit(obj), write=True)
        obj.full_clean()
        return super().save_model(request, obj, form, change)

class OwnedByAdmin(UnitScopedERPAdmin):
    """Populate audit attribution from the authenticated staff session."""
    creator_field = "created_by"

    def save_model(self, request, obj, form, change):
        if not change and not getattr(obj, f"{self.creator_field}_id", None):
            setattr(obj, self.creator_field, request.user)
        super().save_model(request, obj, form, change)


@admin.register(BusinessUnit)
class BusinessUnitAdmin(UnitScopedERPAdmin):
    unit_path = "pk"
    list_display = ("code", "name", "sector", "active")
    list_filter = ("sector", "active")
    search_fields = ("name", "code")


@admin.register(LedgerAccount)
class LedgerAccountAdmin(UnitScopedERPAdmin):
    list_display = ("unit", "code", "name", "category", "active")
    list_filter = ("unit", "category", "active")
    search_fields = ("code", "name")


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 2
    autocomplete_fields = ("account",)

    def has_add_permission(self, request, obj=None):
        return bool(obj is None or obj.status == "draft") and super().has_add_permission(request, obj)

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

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

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
class PartnerAdmin(UnitScopedERPAdmin):
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
class InventoryItemAdmin(UnitScopedERPAdmin):
    list_display = ("sku", "title", "unit", "measure", "reorder_point", "active")
    list_filter = ("unit", "active")
    search_fields = ("sku", "title")


@admin.register(StockMovement)
class StockMovementAdmin(OwnedByAdmin):
    unit_path = "item__unit"
    list_display = ("reference", "item", "direction", "quantity", "status", "confirmed_at")
    list_filter = ("status", "direction", "item__unit")
    search_fields = ("reference", "item__sku")
    readonly_fields = ("status", "confirmed_at", "created_by", "created_at", "updated_at")
    actions = ("confirm_selected",)
    autocomplete_fields = ("item",)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

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
class OfficeLetterAdmin(admin.ModelAdmin):
    """Legacy letters do not have a unit column: strict participant-only scope."""
    list_display = ("number", "subject", "direction", "classification", "assigned_to", "sent_on")
    list_filter = ("direction", "classification", "sent_on")
    search_fields = ("number", "subject")
    readonly_fields = ("created_by", "created_at", "updated_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(Q(created_by=request.user) | Q(assigned_to=request.user))

    def has_view_permission(self, request, obj=None):
        if obj and not request.user.is_superuser and (
            obj.created_by_id != request.user.pk and obj.assigned_to_id != request.user.pk
        ):
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj and not request.user.is_superuser and obj.created_by_id != request.user.pk:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assigned_to":
            from .forms import colleagues
            kwargs["queryset"] = colleagues(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        elif not request.user.is_superuser and obj.created_by_id != request.user.pk:
            raise PermissionDenied("ویرایش نامه دیگری مجاز نیست.")
        obj.full_clean()
        return super().save_model(request, obj, form, change)


@admin.register(WorkTask)
class WorkTaskAdmin(OwnedByAdmin):
    list_display = ("title", "unit", "assigned_to", "priority", "status", "due_on")
    list_filter = ("priority", "status", "unit")
    search_fields = ("title", "description")
    readonly_fields = ("created_by", "created_at", "updated_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.has_perm("enterprise_portal.change_worktask"):
            return qs
        return qs.filter(Q(assigned_to=request.user) | Q(created_by=request.user))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assigned_to":
            from .forms import colleagues
            kwargs["queryset"] = colleagues(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            if not obj.unit_id:
                raise ValidationError("وظیفه باید به یک واحد سازمانی تعیین‌شده تعلق داشته باشد.")
            person = obj.assigned_to
            if not (person.is_superuser or person.pk == request.user.pk or
                    person.ecosystem_memberships.filter(unit=obj.unit, active=True).exists()):
                raise ValidationError("ارجاع وظیفه به فرد خارج از این واحد مجاز نیست.")
        return super().save_model(request, obj, form, change)


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("title", "starts_at", "ends_at", "organizer", "location")
    search_fields = ("title", "location", "agenda")
    filter_horizontal = ("attendees",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(Q(organizer=request.user) | Q(attendees=request.user)).distinct()

    def has_view_permission(self, request, obj=None):
        if obj and not request.user.is_superuser and (
            obj.organizer_id != request.user.pk and not obj.attendees.filter(pk=request.user.pk).exists()
        ):
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj and not request.user.is_superuser and obj.organizer_id != request.user.pk:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return super().has_add_permission(request) and (
            request.user.is_superuser or user_units(request.user).exists()
        )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "attendees":
            from .forms import colleagues
            kwargs["queryset"] = colleagues(request.user)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.organizer = request.user
        elif not request.user.is_superuser and obj.organizer_id != request.user.pk:
            raise PermissionDenied("ویرایش جلسه شخص دیگری مجاز نیست.")
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(ManagementProject)
class ManagementProjectAdmin(UnitScopedERPAdmin):
    list_display = ("code", "title", "unit", "owner", "status", "planned_finish")
    list_filter = ("status", "unit")
    search_fields = ("title", "code")

    def save_model(self, request, obj, form, change):
        if not change and not obj.owner_id:
            obj.owner = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(BudgetPlan)
class BudgetPlanAdmin(UnitScopedERPAdmin):
    list_display = ("title", "unit", "project", "fiscal_year", "amount", "currency", "status")
    list_filter = ("fiscal_year", "unit", "status", "currency")
    search_fields = ("title",)

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(CompanyAsset)
class CompanyAssetAdmin(UnitScopedERPAdmin):
    list_display = ("code", "title", "unit", "acquired_on", "purchase_cost", "currency", "custodian")
    list_filter = ("unit", "currency")
    search_fields = ("code", "title")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "actor", "action", "target")
    list_filter = ("action", "occurred_at")
    search_fields = ("target", "actor__username")
    readonly_fields = ("occurred_at", "actor", "action", "target", "detail")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(actor=request.user)

    def has_view_permission(self, request, obj=None):
        if obj and not request.user.is_superuser and obj.actor_id != request.user.pk:
            return False
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
