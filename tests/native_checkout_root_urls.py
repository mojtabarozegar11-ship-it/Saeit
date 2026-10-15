"""Disposable CI route mapping mirroring production commerce mount; never deployed."""
from django.urls import include, path

urlpatterns = [path("", include("mpw_commerce.urls"))]
