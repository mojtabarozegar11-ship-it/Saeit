"""Unit-isolated administration; publication approval and sending only via audited service."""
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from ecosystem_hub.access import user_units
from .models import Campaign, ChannelAccount, Publication, PublicationEvent, Lead, PerformanceMetric


class UnitScopedAdmin(admin.ModelAdmin):
    def unit_ids(self, request):
        return user_units(request.user).values_list("pk", flat=True)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(unit__in=user_units(request.user))

    def has_delete_permission(self, request, obj=None):
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "unit":
            kwargs["queryset"] = user_units(request.user)
        elif db_field.name == "campaign":
            kwargs["queryset"] = Campaign.objects.filter(unit__in=user_units(request.user))
        elif db_field.name == "contact":
            from company_messaging.models import Contact
            kwargs["queryset"] = Contact.objects.filter(unit__in=user_units(request.user))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not user_units(request.user).filter(pk=obj.unit_id).exists():
            raise PermissionDenied("واحد خارج از دامنه مجوز است.")
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(Campaign)
class CampaignAdmin(UnitScopedAdmin):
    list_display = ("code", "title", "unit", "status", "starts_on", "ends_on", "budget_ceiling_irr")
    list_filter = ("status",)
    search_fields = ("title", "code")
    readonly_fields = ("unit", "code", "owner", "created_at")

    def has_add_permission(self, request):
        return False  # Create with the validated office form.

    def has_change_permission(self, request, obj=None):
        return (request.user.is_superuser or request.user.has_perm("company_marketing.manage_company_campaigns")) and (
            obj is None or user_units(request.user).filter(pk=obj.unit_id).exists()
        )

    def has_view_permission(self, request, obj=None):
        return (request.user.is_superuser or request.user.has_perm("company_marketing.view_campaign")) and (
            obj is None or user_units(request.user).filter(pk=obj.unit_id).exists()
        )


@admin.register(ChannelAccount)
class ChannelAccountAdmin(UnitScopedAdmin):
    list_display = ("title", "unit", "platform", "destination", "is_company_owned", "verified_at", "active")
    search_fields = ("title", "destination")
    list_filter = ("platform", "active", "is_company_owned")
    readonly_fields = ("created_at",)
    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.has_perm("company_marketing.add_channelaccount")
    def has_change_permission(self, request, obj=None):
        return (request.user.is_superuser or request.user.has_perm("company_marketing.change_channelaccount")) and (
            obj is None or user_units(request.user).filter(pk=obj.unit_id).exists()
        )
    def has_view_permission(self, request, obj=None):
        return (request.user.is_superuser or request.user.has_perm("company_marketing.view_channelaccount")) and (
            obj is None or user_units(request.user).filter(pk=obj.unit_id).exists()
        )
    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if not request.user.is_superuser:
            fields += ["is_company_owned", "ownership_evidence", "verified_at"]
        return fields
    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and not change:
            obj.is_company_owned = False
            obj.ownership_evidence = ""
            obj.verified_at = None
        super().save_model(request, obj, form, change)


@admin.register(Lead)
class LeadAdmin(UnitScopedAdmin):
    list_display = ("contact", "unit", "stage", "source", "verified_sale_irr", "sale_evidence_reference")
    list_filter = ("stage",)
    readonly_fields = ("owner", "created_at")
    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.has_perm("company_marketing.add_lead")
    def has_change_permission(self, request, obj=None):
        return (request.user.is_superuser or request.user.has_perm("company_marketing.change_lead")) and (
            obj is None or user_units(request.user).filter(pk=obj.unit_id).exists()
        )
    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj and obj.stage == "won":
            fields += ["unit", "campaign", "contact", "stage", "verified_sale_irr", "sale_evidence_reference"]
        return fields
    def save_model(self, request, obj, form, change):
        if not change:
            obj.owner = request.user
        super().save_model(request, obj, form, change)


@admin.register(PerformanceMetric)
class PerformanceMetricAdmin(admin.ModelAdmin):
    list_display = ("publication", "recorded_on", "impressions", "clicks", "leads", "cost_irr", "evidence_reference")
    readonly_fields = ("recorded_by", "created_at")
    def get_queryset(self, request):
        return super().get_queryset(request).filter(publication__campaign__unit__in=user_units(request.user))
    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.has_perm("company_marketing.add_performancemetric")
    def has_change_permission(self, request, obj=None):
        return False  # Corrections via a separately evidenced record.
    def has_delete_permission(self, request, obj=None):
        return False
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "publication":
            kwargs["queryset"] = Publication.objects.filter(campaign__unit__in=user_units(request.user))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    def save_model(self, request, obj, form, change):
        if not user_units(request.user).filter(pk=obj.publication.campaign.unit_id).exists():
            raise PermissionDenied
        obj.recorded_by = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ("title", "campaign", "channel", "status", "approved_at", "accepted_at", "attempts")
    readonly_fields = ("key", "campaign", "channel", "title", "content", "landing_url",
                       "scheduled_at", "rights_reference", "status", "content_sha256",
                       "approved_by", "approved_at", "provider_reference", "accepted_at",
                       "attempts", "error_code", "created_by", "created_at")
    actions = None
    def get_queryset(self, request):
        return super().get_queryset(request).filter(campaign__unit__in=user_units(request.user))
    def has_view_permission(self, request, obj=None):
        return (request.user.is_superuser or request.user.has_perm("company_marketing.view_publication")) and (
            obj is None or user_units(request.user).filter(pk=obj.campaign.unit_id).exists()
        )
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PublicationEvent)
class PublicationEventAdmin(admin.ModelAdmin):
    list_display = ("publication", "code", "created_at")
    readonly_fields = ("publication", "code", "created_at")
    actions = None
    def get_queryset(self, request):
        return super().get_queryset(request).filter(publication__campaign__unit__in=user_units(request.user))
    def has_view_permission(self, request, obj=None):
        return (request.user.is_superuser or request.user.has_perm("company_marketing.view_publicationevent")) and (
            obj is None or user_units(request.user).filter(pk=obj.publication.campaign.unit_id).exists()
        )
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
