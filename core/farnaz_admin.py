from django.contrib import admin

from .models import FarnazInquiry, FarnazOffer, FarnazProject, FarnazService


@admin.register(FarnazService)
class FarnazServiceAdmin(admin.ModelAdmin):
    list_display = ("title", "active", "starting_price", "sort_order", "updated_at")
    list_filter = ("active",)
    search_fields = ("title", "summary", "details")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("sort_order", "id")


@admin.register(FarnazProject)
class FarnazProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "discipline", "is_concept", "active", "sort_order")
    list_filter = ("active", "is_concept", "discipline")
    search_fields = ("title", "summary")
    ordering = ("sort_order", "id")


@admin.register(FarnazOffer)
class FarnazOfferAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "price", "checkout_enabled", "active", "sort_order")
    list_filter = ("kind", "active", "checkout_enabled")
    search_fields = ("title", "description")
    ordering = ("sort_order", "id")


@admin.register(FarnazInquiry)
class FarnazInquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "category", "status", "created_at")
    list_filter = ("status", "category", "created_at")
    search_fields = ("name", "phone", "email", "message")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
