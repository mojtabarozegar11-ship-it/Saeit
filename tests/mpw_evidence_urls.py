"""Only test the command center route; do not import live production URLs."""
from django.contrib import admin
from django.urls import path, include
urlpatterns=[
    path("admin/",admin.site.urls),
    path("staff/command-center/",include("command_center.urls")),
]
