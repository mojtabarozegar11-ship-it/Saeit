from django.contrib import admin
from django.db.models import Q
from ecosystem_hub.access import user_units
from .models import Contact, Message, MessageEvent


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "email", "phone_e164", "active", "suppressed")
    list_filter = ("unit", "active", "suppressed")
    search_fields = ("name", "email", "phone_e164")
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(unit__in=user_units(request.user))

    def has_module_permission(self, request):
        return request.user.is_superuser or request.user.has_perm("company_messaging.manage_company_contacts")

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request) and (obj is None or
                user_units(request.user).filter(pk=obj.unit_id).exists())

    def has_add_permission(self, request):
        return self.has_module_permission(request) and user_units(request.user).exists()

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "unit":
            kwargs["queryset"] = user_units(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not user_units(request.user).filter(pk=obj.unit_id).exists():
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "unit", "channel", "sender", "status", "created_at")
    list_filter = ("channel", "status")
    readonly_fields = ("key", "unit", "sender", "contact", "recipient_user", "channel",
                       "subject", "body", "status", "scheduled_at", "accepted_at",
                       "attempts", "external_reference", "error_code", "created_at")
    search_fields = ("subject",)
    actions = None

    def get_queryset(self, request):
        qs = super().get_queryset(request).filter(unit__in=user_units(request.user))
        if request.user.is_superuser:
            return qs
        return qs.filter(Q(sender=request.user) | Q(recipient_user=request.user))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        if obj is not None and not self.get_queryset(request).filter(pk=obj.pk).exists():
            return False
        return super().has_view_permission(request, obj)


@admin.register(MessageEvent)
class MessageEventAdmin(admin.ModelAdmin):
    list_display = ("message_id", "code", "created_at")
    readonly_fields = ("message", "code", "created_at")
    actions = None

    def get_queryset(self, request):
        qs = super().get_queryset(request).filter(message__unit__in=user_units(request.user))
        if request.user.is_superuser:
            return qs
        if not request.user.has_perm("company_messaging.view_company_message_audit"):
            return qs.none()
        return qs.filter(Q(message__sender=request.user) | Q(message__recipient_user=request.user))

    def has_view_permission(self, request, obj=None):
        if not (request.user.is_superuser or request.user.has_perm("company_messaging.view_company_message_audit")):
            return False
        return obj is None or self.get_queryset(request).filter(pk=obj.pk).exists()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
