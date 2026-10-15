"""Scoped routes required by the release gate tests; no production URL import."""
from django.contrib import admin
from django.urls import path
from core.commerce_views import store_home

urlpatterns = [
    path("admin/", admin.site.urls),
    path("store/", store_home, name="store"),
]
