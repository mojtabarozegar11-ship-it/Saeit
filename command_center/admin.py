"""Django admin offers inspection; all transitions require the scoped operations desk."""
from django.contrib import admin
from .models import MpwRecord


@admin.register(MpwRecord)
class MpwRecordAdmin(admin.ModelAdmin):
    list_display = ("key","kind","page_path","state","revision","published_at","updated_at")
    list_filter = ("kind","state","page_path")
    search_fields = ("key","title","page_path")
    readonly_fields = ("tenant","kind","key","page_path","title","draft",
                       "published_snapshot","state","revision","quality_note",
                       "quality_evidence","approval_evidence","created_at",
                       "updated_at","published_at")
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
