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


from .models import WorkItem, InternalMessage, PrivateAuction


@admin.register(WorkItem)
class WorkItemAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "resolution_reference", "status", "priority", "assignee", "due_at", "created_at")
    list_filter = ("status", "priority")
    search_fields = ("title", "description", "source_type", "source_id", "resolution_reference", "project__title")


@admin.register(InternalMessage)
class InternalMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "sender", "recipient", "read_at", "created_at")
    list_filter = ("read_at",)
    search_fields = ("subject", "body")
    readonly_fields = ("created_at",)


@admin.register(PrivateAuction)
class PrivateAuctionAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "minimum_price", "starts_at", "ends_at", "created_by")
    list_filter = ("status",)
    search_fields = ("title", "description")
