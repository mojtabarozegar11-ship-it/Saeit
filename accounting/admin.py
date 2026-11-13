from django import forms
from django.contrib import admin
from django.forms.models import BaseInlineFormSet
from django.core.exceptions import ValidationError
from .models import Account, JournalEntry, JournalLine


class JournalLineInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(form.errors for form in self.forms):
            return
        if self.instance.status != JournalEntry.Status.POSTED:
            return
        debit = sum((form.cleaned_data.get("debit") or 0 for form in self.forms if not form.cleaned_data.get("DELETE")), 0)
        credit = sum((form.cleaned_data.get("credit") or 0 for form in self.forms if not form.cleaned_data.get("DELETE")), 0)
        if debit <= 0 or debit != credit:
            raise forms.ValidationError("سند قطعی باید تراز باشد؛ جمع بدهکار و بستانکار برابر نیست.")


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 2
    formset = JournalLineInlineFormSet


class JournalLineAdminForm(forms.ModelForm):
    class Meta:
        model = JournalLine
        fields = "__all__"

    def clean_entry(self):
        entry = self.cleaned_data["entry"]
        if entry.status == JournalEntry.Status.POSTED:
            raise forms.ValidationError("افزودن یا ویرایش ردیف سند قطعی مجاز نیست.")
        return entry


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

    # Once posted, a journal must be reversed by a separate entry, never edited or removed.
    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.status == JournalEntry.Status.POSTED:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.status == JournalEntry.Status.POSTED:
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        # Do not trust a submitted status field: check the original persisted state.
        if change and JournalEntry.objects.filter(pk=obj.pk, status=JournalEntry.Status.POSTED).exists():
            raise ValidationError("سند قطعی قابل ویرایش نیست؛ اصلاح باید با سند معکوس ثبت شود.")
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        if obj.status == JournalEntry.Status.POSTED:
            raise ValidationError("حذف سند قطعی ممنوع است.")
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        if queryset.filter(status=JournalEntry.Status.POSTED).exists():
            raise ValidationError("حذف گروهی اسناد قطعی ممنوع است.")
        super().delete_queryset(request, queryset)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if form.instance.status == JournalEntry.Status.POSTED:
            form.instance.validate_balanced()


@admin.register(JournalLine)
class JournalLineAdmin(admin.ModelAdmin):
    form = JournalLineAdminForm
    actions = None
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

    def delete_queryset(self, request, queryset):
        if queryset.filter(entry__status=JournalEntry.Status.POSTED).exists():
            raise ValidationError("حذف گروهی ردیف‌های اسناد قطعی مجاز نیست.")
        super().delete_queryset(request, queryset)
