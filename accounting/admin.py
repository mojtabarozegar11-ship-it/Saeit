from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import Account, JournalEntry, JournalLine


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 2


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("code", "name")


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("reference", "occurred_on", "memo", "status", "created_by")
    list_filter = ("status", "occurred_on")
    search_fields = ("reference", "memo")
    inlines = (JournalLineInline,)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if form.instance.status == JournalEntry.Status.POSTED:
            form.instance.validate_balanced()


@admin.register(JournalLine)
class JournalLineAdmin(admin.ModelAdmin):
    list_display = ("entry", "account", "debit", "credit")
    list_filter = ("account",)

    def save_model(self, request, obj, form, change):
        if obj.entry.status == JournalEntry.Status.POSTED:
            raise ValidationError("سند قطعی قابل تغییر نیست.")
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and not (obj and obj.entry.status == JournalEntry.Status.POSTED)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (obj and obj.entry.status == JournalEntry.Status.POSTED)
